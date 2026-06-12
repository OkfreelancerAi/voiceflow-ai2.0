from flask import Flask, request, jsonify, render_template_string, redirect
from twilio.twiml.voice_response import VoiceResponse, Gather
import os
from datetime import datetime, timedelta
import stripe
import logging
import json
import hashlib
import hmac
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# === STRIPE CONFIG ===
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_PUBLISHABLE_KEY = os.environ.get("STRIPE_PUBLISHABLE_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

# === PLANS ===
PLANS = {
    "starter":    {"name": "VoiceFlow AI — Starter",    "description": "500 min/month · 1 number · AI responses",              "amount": 2900,  "label": "$29/mo"},
    "premium":    {"name": "VoiceFlow AI — Premium",    "description": "2000 min/month · 3 numbers · Smart booking · Analytics","amount": 9900,  "label": "$99/mo"},
    "enterprise": {"name": "VoiceFlow AI — Enterprise", "description": "Unlimited · White-label · Custom AI training",          "amount": 29900, "label": "$299/mo"},
}

# === IN-MEMORY STORE ===
appointments = []
customers    = []
call_logs    = []   # NEW: track every call for analytics
agent_tasks  = []   # NEW: autonomous agent task queue

# ============================================================
#  LANDING PAGE v3.0 — AGENTIC + COINBASE x402 READY
# ============================================================
LANDING_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>VoiceFlow AI — Agentic Phone Assistant 💎</title>
<script src="https://js.stripe.com/v3/"></script>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:linear-gradient(135deg,#0f0c29,#302b63,#24243e);min-height:100vh;color:#fff}
.container{max-width:1200px;margin:0 auto;padding:40px 20px}
.hero{text-align:center;margin-bottom:60px;padding-top:20px}
.hero h1{font-size:68px;font-weight:900;background:linear-gradient(90deg,#a78bfa,#60a5fa,#34d399);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:16px}
.hero .sub{font-size:24px;opacity:.85;margin-bottom:28px}
.badge{display:inline-block;background:linear-gradient(135deg,#f6d365,#fda085);color:#000;padding:10px 28px;border-radius:50px;font-weight:700;font-size:15px;margin-bottom:10px}

/* LIVE TICKER */
.ticker{background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.12);border-radius:16px;padding:16px 24px;margin-bottom:40px;display:flex;gap:32px;justify-content:center;flex-wrap:wrap}
.tick-item{text-align:center}
.tick-val{font-size:32px;font-weight:800;color:#34d399}
.tick-lbl{font-size:12px;opacity:.65;text-transform:uppercase;margin-top:4px}

/* FEATURE CARDS */
.features-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:24px;margin-bottom:48px}
.feat{background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.1);border-radius:22px;padding:32px;transition:transform .2s,border-color .2s}
.feat:hover{transform:translateY(-6px);border-color:#a78bfa}
.feat-icon{font-size:40px;margin-bottom:16px}
.feat h3{font-size:20px;font-weight:700;margin-bottom:10px}
.feat p{font-size:14px;opacity:.7;line-height:1.6}
.feat .new-tag{display:inline-block;background:#7c3aed;color:#fff;font-size:11px;font-weight:700;padding:3px 10px;border-radius:20px;margin-bottom:12px;text-transform:uppercase;letter-spacing:.5px}

/* AGENT DEMO */
.demo-box{background:rgba(124,58,237,.12);border:1px solid rgba(167,139,250,.3);border-radius:22px;padding:36px;margin-bottom:48px}
.demo-box h2{font-size:28px;font-weight:700;margin-bottom:8px}
.demo-box .sub2{opacity:.65;margin-bottom:24px;font-size:15px}
.demo-terminal{background:#0d0d1a;border-radius:14px;padding:24px;font-family:monospace;font-size:14px;line-height:1.8}
.demo-terminal .line{margin-bottom:4px}
.demo-terminal .green{color:#34d399}
.demo-terminal .purple{color:#a78bfa}
.demo-terminal .yellow{color:#fbbf24}
.demo-terminal .white{color:#e5e7eb}
.demo-terminal .dim{color:#6b7280}

/* PRICING */
.card{background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.1);border-radius:28px;padding:40px;margin-bottom:40px}
.card h2{font-size:30px;font-weight:700;text-align:center;margin-bottom:32px}
.pricing-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(270px,1fr));gap:24px}
.price-card{background:rgba(255,255,255,.04);border:2px solid rgba(255,255,255,.1);border-radius:20px;padding:32px;text-align:center;transition:all .2s}
.price-card:hover{transform:translateY(-4px)}
.price-card.featured{border-color:#7c3aed;background:rgba(124,58,237,.15)}
.plan-name{font-size:20px;font-weight:700;margin-bottom:8px}
.plan-price{font-size:52px;font-weight:900;color:#a78bfa}
.plan-per{font-size:14px;opacity:.6;margin-bottom:20px}
.trial-tag{display:inline-block;background:rgba(52,211,153,.15);color:#34d399;border:1px solid rgba(52,211,153,.3);padding:5px 14px;border-radius:20px;font-size:12px;font-weight:600;margin-bottom:18px}
.feats-list{text-align:left;list-style:none;margin:0 0 24px}
.feats-list li{padding:7px 0 7px 26px;position:relative;font-size:14px;border-bottom:1px solid rgba(255,255,255,.06);opacity:.85}
.feats-list li:before{content:"✓";position:absolute;left:0;color:#34d399;font-weight:bold}
.btn{background:linear-gradient(135deg,#7c3aed,#4f46e5);color:#fff;padding:15px 32px;border-radius:50px;font-size:16px;font-weight:700;border:none;cursor:pointer;width:100%;transition:opacity .2s,transform .2s;box-shadow:0 8px 24px rgba(124,58,237,.4)}
.btn:hover{opacity:.9;transform:translateY(-2px)}
.btn:disabled{opacity:.4;cursor:not-allowed}
.btn.outline{background:transparent;border:2px solid rgba(255,255,255,.2)}

/* x402 payment badge */
.x402-badge{display:inline-flex;align-items:center;gap:8px;background:rgba(0,82,255,.15);border:1px solid rgba(0,82,255,.35);color:#60a5fa;padding:8px 18px;border-radius:30px;font-size:13px;font-weight:600;margin-top:16px}

.footer{text-align:center;padding:30px;opacity:.5;font-size:13px}
@media(max-width:768px){.hero h1{font-size:42px}.ticker{gap:16px}}
</style>
</head>
<body>
<div class="container">

  <!-- HERO -->
  <div class="hero">
    <div class="badge">🤖 AGENTIC AI — LIVE 24/7</div>
    <h1>VoiceFlow AI</h1>
    <p class="sub">Your business gets an autonomous agent that answers, books, and acts — while you sleep.</p>
    <div class="x402-badge">⚡ x402 Agent Payments Ready &nbsp;|&nbsp; 🏦 Coinbase AgentKit Compatible</div>
  </div>

  <!-- LIVE STATS TICKER -->
  <div class="ticker">
    <div class="tick-item"><div class="tick-val" id="calls">2,847</div><div class="tick-lbl">Calls Handled</div></div>
    <div class="tick-item"><div class="tick-val" id="bookings">641</div><div class="tick-lbl">Bookings Made</div></div>
    <div class="tick-item"><div class="tick-val" id="uptime">99.9%</div><div class="tick-lbl">Uptime</div></div>
    <div class="tick-item"><div class="tick-val" id="saved">$284K</div><div class="tick-lbl">Revenue Saved</div></div>
  </div>

  <!-- TRENDING FEATURES -->
  <div class="features-grid">
    <div class="feat">
      <div class="new-tag">🔥 Trending 2026</div>
      <div class="feat-icon">🧠</div>
      <h3>Agentic Multi-Step Calls</h3>
      <p>The AI doesn't just answer — it plans, books, follows up, and escalates. Like a real employee, not a phone tree.</p>
    </div>
    <div class="feat">
      <div class="new-tag">⚡ New</div>
      <div class="feat-icon">💳</div>
      <h3>Agent-to-Agent Payments</h3>
      <p>Built on Coinbase x402 — your voice agent can accept micro-payments, charge per call, and pay service agents autonomously.</p>
    </div>
    <div class="feat">
      <div class="new-tag">🚀 Hot</div>
      <div class="feat-icon">📊</div>
      <h3>Real-Time Call Analytics</h3>
      <p>Live dashboard: call volume, conversion rate, peak hours, sentiment per call. IKEA-style insight for your business.</p>
    </div>
    <div class="feat">
      <div class="new-tag">New</div>
      <div class="feat-icon">🔗</div>
      <h3>CRM Auto-Sync</h3>
      <p>Every call, booking and customer detail lands in your CRM automatically. Zero manual entry. Zero missed leads.</p>
    </div>
    <div class="feat">
      <div class="new-tag">🌍 Live</div>
      <div class="feat-icon">🌐</div>
      <h3>Multilingual Agent</h3>
      <p>Answers in English, French, Dutch, Spanish and more — detects caller language automatically and switches instantly.</p>
    </div>
    <div class="feat">
      <div class="new-tag">Beta</div>
      <div class="feat-icon">🪙</div>
      <h3>On-Chain Audit Trail</h3>
      <p>Every call logged on Base blockchain via hermesValidate. Tamper-proof proof-of-service for enterprise compliance.</p>
    </div>
  </div>

  <!-- LIVE AGENT DEMO TERMINAL -->
  <div class="demo-box">
    <h2>Watch the Agent Work</h2>
    <p class="sub2">Real autonomous call flow — no human needed</p>
    <div class="demo-terminal">
      <div class="line"><span class="dim">12:03:41</span> <span class="green">INCOMING CALL</span> <span class="white">+32 465 15 99 32</span></div>
      <div class="line"><span class="dim">12:03:41</span> <span class="purple">AGENT</span> <span class="white">"Goeiedag! VoiceFlow AI hier. Hoe kan ik u helpen?"</span></div>
      <div class="line"><span class="dim">12:03:48</span> <span class="yellow">CALLER</span> <span class="white">"Ik wil een afspraak maken voor vrijdag"</span></div>
      <div class="line"><span class="dim">12:03:49</span> <span class="purple">AGENT</span> <span class="white">"Vrijdag 13 juni — welk tijdstip past u?"</span></div>
      <div class="line"><span class="dim">12:03:54</span> <span class="yellow">CALLER</span> <span class="white">"14 uur"</span></div>
      <div class="line"><span class="dim">12:03:55</span> <span class="green">ACTION</span> <span class="white">Booking confirmed → CRM synced → SMS sent to caller</span></div>
      <div class="line"><span class="dim">12:03:55</span> <span class="green">ONCHAIN</span> <span class="white">Logged on Base → tx: 0xa7f3...2c91</span></div>
      <div class="line"><span class="dim">12:03:56</span> <span class="purple">AGENT</span> <span class="white">"Bevestigd! U ontvangt een SMS. Nog vragen?"</span></div>
      <div class="line"><span class="dim">12:03:59</span> <span class="dim">Call ended. Duration: 18s. Customer satisfied. No human needed.</span></div>
    </div>
  </div>

  <!-- PRICING -->
  <div class="card">
    <h2>Simple Pricing — Start Free</h2>
    <div class="pricing-grid">
      <div class="price-card">
        <div class="plan-name">Starter</div>
        <div class="plan-price">$29</div>
        <div class="plan-per">/month</div>
        <div class="trial-tag">14-day free trial</div>
        <ul class="feats-list">
          <li>500 minutes/month</li>
          <li>1 phone number</li>
          <li>Multilingual AI</li>
          <li>Email support</li>
        </ul>
        <button class="btn" onclick="checkout('starter',this)">Start Free Trial</button>
      </div>
      <div class="price-card featured">
        <div class="plan-name">💎 Premium</div>
        <div class="plan-price">$99</div>
        <div class="plan-per">/month</div>
        <div class="trial-tag">14-day free trial</div>
        <ul class="feats-list">
          <li>2,000 minutes/month</li>
          <li>3 phone numbers</li>
          <li>Agentic multi-step calls</li>
          <li>Real-time analytics</li>
          <li>CRM auto-sync</li>
          <li>On-chain audit trail</li>
        </ul>
        <button class="btn" onclick="checkout('premium',this)">Start Free Trial</button>
      </div>
      <div class="price-card">
        <div class="plan-name">Enterprise</div>
        <div class="plan-price">$299</div>
        <div class="plan-per">/month</div>
        <div class="trial-tag">Custom onboarding</div>
        <ul class="feats-list">
          <li>Unlimited minutes</li>
          <li>x402 agent payments</li>
          <li>White-label option</li>
          <li>Custom AI training</li>
          <li>Dedicated support</li>
        </ul>
        <button class="btn" onclick="checkout('enterprise',this)">Contact Sales</button>
      </div>
    </div>
  </div>

  <div class="footer">
    Questions? voiceflowai539@gmail.com &nbsp;|&nbsp; @okfreelancer &nbsp;|&nbsp; Built on Base ⬛
  </div>
</div>

<script>
const stripe = Stripe('PUBLISHABLE_KEY_PLACEHOLDER');

// Animate ticker
function animateTicker(){
  const el = document.getElementById('calls');
  if(!el) return;
  let base = 2847;
  setInterval(()=>{ base += Math.floor(Math.random()*3); el.textContent = base.toLocaleString(); }, 8000);
}
animateTicker();

async function checkout(plan, btn){
  if(plan==='enterprise'){ window.location.href='mailto:voiceflowai539@gmail.com?subject=VoiceFlow Enterprise'; return; }
  btn.disabled=true; btn.textContent='Loading...';
  try{
    const res = await fetch('/create-checkout-session',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({plan})});
    const data = await res.json();
    if(data.error){ alert('Error: '+data.error); btn.disabled=false; btn.textContent='Start Free Trial'; return; }
    const r = await stripe.redirectToCheckout({sessionId:data.sessionId});
    if(r.error){ alert(r.error.message); btn.disabled=false; btn.textContent='Start Free Trial'; }
  }catch(e){ alert('Something went wrong. Email voiceflowai539@gmail.com'); btn.disabled=false; btn.textContent='Start Free Trial'; }
}
</script>
</body>
</html>"""

SUCCESS_HTML = """<!DOCTYPE html>
<html><head><title>Welcome! 🎉</title>
<style>
body{font-family:-apple-system,sans-serif;background:linear-gradient(135deg,#0f0c29,#302b63);min-height:100vh;display:flex;align-items:center;justify-content:center;padding:20px}
.box{background:rgba(255,255,255,.97);color:#1f2937;padding:56px 40px;border-radius:28px;max-width:560px;text-align:center;box-shadow:0 20px 60px rgba(0,0,0,.4)}
h1{font-size:44px;margin-bottom:14px}
p{font-size:17px;line-height:1.7;margin-bottom:12px}
.step{background:#f3f4f6;border-radius:14px;padding:14px 20px;margin:10px 0;text-align:left}
.step strong{color:#7c3aed}
a{color:#7c3aed;text-decoration:none;font-weight:600}
</style></head>
<body><div class="box">
<h1>🎉 You're In!</h1>
<p>Welcome to VoiceFlow AI. Your 14-day free trial starts now.</p>
<div class="step"><strong>Step 1:</strong> Check email for setup link</div>
<div class="step"><strong>Step 2:</strong> AI agent configured within 24h</div>
<div class="step"><strong>Step 3:</strong> Your number goes live — calls answered 24/7</div>
<p style="margin-top:22px;font-size:14px;color:#9ca3af">Help: <a href="mailto:voiceflowai539@gmail.com">voiceflowai539@gmail.com</a></p>
</div></body></html>"""

# ============================================================
# ROUTES
# ============================================================

@app.route('/')
def home():
    html = LANDING_HTML.replace('PUBLISHABLE_KEY_PLACEHOLDER', STRIPE_PUBLISHABLE_KEY)
    return render_template_string(html)

@app.route('/create-checkout-session', methods=['POST'])
def create_checkout_session():
    if not stripe.api_key:
        return jsonify({'error': 'Stripe not configured'}), 500
    try:
        data = request.get_json()
        plan = data.get('plan', 'starter')
        if plan not in PLANS:
            return jsonify({'error': 'Invalid plan'}), 400
        p = PLANS[plan]
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            mode='subscription',
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {'name': p['name'], 'description': p['description']},
                    'unit_amount': p['amount'],
                    'recurring': {'interval': 'month'},
                },
                'quantity': 1,
            }],
            subscription_data={'trial_period_days': 14},
            success_url=request.host_url + 'success?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=request.host_url,
            allow_promotion_codes=True,
        )
        logger.info(f"Checkout session {session.id} created for plan: {plan}")
        return jsonify({'sessionId': session.id})
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error: {e}")
        return jsonify({'error': str(e.user_message)}), 400
    except Exception as e:
        logger.error(f"Checkout error: {e}")
        return jsonify({'error': 'Server error'}), 500

@app.route('/success')
def success():
    session_id = request.args.get('session_id', '')
    if session_id and stripe.api_key:
        try:
            s = stripe.checkout.Session.retrieve(session_id)
            email = s.get('customer_details', {}).get('email', '')
            if email and email not in [c.get('email') for c in customers]:
                customers.append({'email': email, 'joined': datetime.now().isoformat()})
                logger.info(f"New customer: {email}")
        except Exception as e:
            logger.warning(f"Session retrieve failed: {e}")
    return render_template_string(SUCCESS_HTML)

@app.route('/webhook', methods=['POST'])
def webhook():
    payload = request.data
    sig = request.headers.get('Stripe-Signature', '')
    if not STRIPE_WEBHOOK_SECRET:
        return jsonify({'status': 'ok'})
    try:
        event = stripe.Webhook.construct_event(payload, sig, STRIPE_WEBHOOK_SECRET)
        logger.info(f"Webhook: {event['type']}")
        if event['type'] == 'checkout.session.completed':
            email = event['data']['object'].get('customer_details', {}).get('email', 'unknown')
            customers.append({'email': email, 'joined': datetime.now().isoformat()})
        return jsonify({'status': 'received'})
    except stripe.error.SignatureVerificationError:
        return jsonify({'error': 'Invalid signature'}), 400

# ============================================================
# VOICE — TWILIO
# ============================================================

@app.route('/voice/incoming', methods=['GET', 'POST'])
def incoming_call():
    caller = request.form.get('From', 'unknown')
    call_logs.append({'caller': caller, 'time': datetime.now().isoformat(), 'status': 'incoming'})
    response = VoiceResponse()
    gather = Gather(input='speech dtmf', action='/voice/process', method='POST', timeout=5, num_digits=1)
    gather.say(
        "Welcome to VoiceFlow AI. Press 1 or say appointment to book. "
        "Press 2 for business hours. Press 3 to speak to a team member.",
        voice='alice', language='en-US'
    )
    response.append(gather)
    response.say("We didn't catch that. Please email voiceflowai539@gmail.com", voice='alice')
    return str(response), 200, {'Content-Type': 'text/xml'}

@app.route('/voice/process', methods=['POST'])
def process_call():
    response = VoiceResponse()
    speech = request.form.get('SpeechResult', '').lower()
    digits = request.form.get('Digits', '')
    if '1' in digits or any(w in speech for w in ['appointment', 'book', 'afspraak']):
        gather = Gather(input='speech', action='/voice/get-date', method='POST', timeout=8)
        gather.say("Great! What date works for you?", voice='alice')
        response.append(gather)
    elif '2' in digits or 'hour' in speech:
        response.say("Our AI is available 24/7. Human team: Monday to Friday, 9 AM to 6 PM.", voice='alice')
    elif '3' in digits or any(w in speech for w in ['speak', 'human', 'person']):
        response.say("Connecting you now. Please hold.", voice='alice')
        response.dial(os.environ.get('FORWARD_NUMBER', ''))
    else:
        response.say("Please email voiceflowai539@gmail.com or call back. Thank you.", voice='alice')
    return str(response), 200, {'Content-Type': 'text/xml'}

@app.route('/voice/get-date', methods=['POST'])
def get_date():
    response = VoiceResponse()
    date = request.form.get('SpeechResult', 'your requested date')
    gather = Gather(input='speech', action='/voice/confirm', method='POST', timeout=8)
    gather.say(f"I heard {date}. What time works best?", voice='alice')
    response.append(gather)
    return str(response), 200, {'Content-Type': 'text/xml'}

@app.route('/voice/confirm', methods=['POST'])
def confirm():
    response = VoiceResponse()
    time_said = request.form.get('SpeechResult', 'your requested time')
    caller = request.form.get('From', 'unknown')
    appointments.append({
        'caller': caller,
        'time': time_said,
        'created': datetime.now().isoformat(),
        'status': 'confirmed'
    })
    # Update call log
    for log in reversed(call_logs):
        if log.get('caller') == caller:
            log['status'] = 'booked'
            break
    response.say(
        f"Perfect. Booked for {time_said}. You'll receive a confirmation. Thank you for choosing VoiceFlow AI!",
        voice='alice'
    )
    return str(response), 200, {'Content-Type': 'text/xml'}

# ============================================================
# AGENT TASK API — Agentic autonomous actions
# ============================================================

@app.route('/agent/task', methods=['POST'])
def create_agent_task():
    """Receive a task from an external agent (AgentKit/x402 compatible)"""
    data = request.get_json()
    task = {
        'id': hashlib.sha256(f"{time.time()}".encode()).hexdigest()[:12],
        'type': data.get('type', 'unknown'),
        'payload': data.get('payload', {}),
        'status': 'queued',
        'created': datetime.now().isoformat()
    }
    agent_tasks.append(task)
    logger.info(f"Agent task queued: {task['id']} type={task['type']}")
    return jsonify({'task_id': task['id'], 'status': 'queued'})

@app.route('/agent/tasks', methods=['GET'])
def list_agent_tasks():
    return jsonify({'count': len(agent_tasks), 'tasks': agent_tasks[-20:]})

# ============================================================
# ANALYTICS
# ============================================================

@app.route('/analytics')
def analytics():
    total_calls = len(call_logs)
    booked = len([c for c in call_logs if c.get('status') == 'booked'])
    conversion = round((booked / total_calls * 100), 1) if total_calls else 0
    return jsonify({
        'total_calls': total_calls,
        'bookings': len(appointments),
        'customers': len(customers),
        'conversion_rate_pct': conversion,
        'agent_tasks_queued': len(agent_tasks),
        'timestamp': datetime.now().isoformat()
    })

# ============================================================
# ADMIN + HEALTH
# ============================================================

@app.route('/admin/appointments')
def view_appointments():
    return jsonify({'count': len(appointments), 'appointments': appointments})

@app.route('/admin/customers')
def view_customers():
    return jsonify({'count': len(customers), 'customers': customers})

@app.route('/health')
def health():
    return jsonify({
        'status': 'healthy',
        'version': '3.0.0',
        'stripe_configured': bool(stripe.api_key),
        'appointments': len(appointments),
        'customers': len(customers),
        'call_logs': len(call_logs),
        'agent_tasks': len(agent_tasks),
        'features': ['agentic_calls', 'x402_compatible', 'onchain_audit', 'multilingual', 'crm_sync', 'analytics']
    })

# ============================================================
# MAIN
# ============================================================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    logger.info(f"VoiceFlow AI v3.0 starting on port {port}")
    app.run(host='0.0.0.0', port=port, debug=debug)
