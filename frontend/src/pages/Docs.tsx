export default function Docs() {
  return (
    <div className="docs">
      <div className="page-head">
        <div>
          <h1>Documentation</h1>
          <div className="page-sub">How to run a phishing-awareness simulation with VoltPhish</div>
        </div>
      </div>

      <div className="toc">
        <a href="#quickstart">Quick start</a>
        <a href="#templates">Templates</a>
        <a href="#pages">Landing Pages</a>
        <a href="#groups">Groups</a>
        <a href="#profiles">Sending Profiles</a>
        <a href="#campaigns">Campaigns</a>
        <a href="#tracking">Tracking</a>
        <a href="#webhooks">Webhooks</a>
        <a href="#api">API Keys</a>
      </div>

      <h2 id="quickstart">1. Quick start (5 steps)</h2>
      <ol>
        <li>Create an <strong>Email Template</strong> — the message recipients receive.</li>
        <li>(Optional) Create a <strong>Landing Page</strong> — the page shown after a click.</li>
        <li>Create a <strong>Group</strong> of target recipients.</li>
        <li>Create a <strong>Sending Profile</strong> — SMTP server or an Email API (Brevo/SendGrid…). Use{" "}
          <strong>Verify</strong> + <strong>Send test</strong> to confirm it works.</li>
        <li>Create a <strong>Campaign</strong> tying them together, then <strong>Launch</strong>.</li>
      </ol>

      <h2 id="templates">2. Email Templates</h2>
      <p>Templates support personalization tokens rendered per recipient:</p>
      <pre>{`{{.FirstName}}  {{.LastName}}  {{.Email}}  {{.Position}}
{{.URL}}       click-tracking link (records a click, then redirects)
{{.Tracker}}   open-tracking pixel (auto-added if you omit it)
{{.RId}}       the recipient's unique tracking id`}</pre>
      <ul>
        <li><strong>Import from .eml</strong> — paste a raw email and VoltPhish fills subject/body for you.</li>
        <li><strong>Send test</strong> — deliver one <code>[TEST]</code> email to yourself to verify SMTP + rendering.</li>
        <li><strong>Attachments</strong> — attach lure documents (PDF/Office/etc., ≤5 MB each). Executables are blocked.</li>
        <li>Put your phishing link on any text with <code>{`{{.URL}}`}</code> as the href.</li>
      </ul>

      <h2 id="pages">3. Landing Pages</h2>
      <ul>
        <li>Write custom HTML, or <strong>Import Site</strong> from a URL to clone a login page (the fetch is
          SSRF-guarded — internal/metadata addresses are blocked).</li>
        <li>Any <code>&lt;form&gt;</code> on the page is automatically captured: VoltPhish rewrites the form to
          post back to its tracker, no matter what action you wrote.</li>
        <li><strong>Passwords are never stored.</strong> A submission is recorded as an event for your metrics; the
          password value is discarded.</li>
        <li>Set a <strong>Redirect after submit</strong> to send users to a teaching/awareness page.</li>
      </ul>

      <h2 id="groups">4. Groups &amp; Targets</h2>
      <p>Add recipients one by one, or paste them in bulk — one per line:</p>
      <pre>{`alice@example.com, Alice, Ng, Finance
bob@example.com, Bob, Lee, Sales`}</pre>

      <h2 id="profiles">5. Sending Profiles</h2>
      <p>Two delivery types — pick "Delivery type" at the top of the profile form:</p>
      <ul>
        <li><strong>SMTP server</strong> — host/port + optional username/password (encrypted at rest). STARTTLS (587)
          or implicit SSL (465); type the port and the TLS options auto-select. Use <strong>Verify</strong> to
          connect + authenticate without sending.</li>
        <li><strong>Email API (recommended if SMTP ports are blocked)</strong> — sends over <strong>HTTPS (port 443)</strong>,
          which firewalls rarely block. Supported: Brevo, SendGrid, Resend, Postmark, Mailgun. Sign up, verify your
          sender/domain <em>in that provider</em>, paste the API key, and hit <strong>Verify</strong>. Mailgun also needs a
          sending domain.</li>
      </ul>
      <p className="hint">
        Whichever you use, <strong>Verify</strong> and <strong>Send test</strong> exercise the real service, so you
        can confirm credentials before launching a campaign.
      </p>
      <h3>"Sent" vs "delivered"</h3>
      <p>
        A recipient marked <strong>sent</strong> means the mail server/provider <em>accepted</em> the message. Final
        delivery to the inbox still depends on the provider and recipient (a new provider account may be pending
        activation, or mail may be filtered). Check your provider's dashboard for delivery/bounce status.
      </p>

      <h2 id="campaigns">6. Campaigns &amp; Scheduling</h2>
      <ul>
        <li>Pick template, group, profile, and (optionally) a landing page.</li>
        <li><strong>Phishing URL</strong> — the base URL recipients' links resolve to. In production this must be a
          host they can reach and you're authorized to use.</li>
        <li><strong>Schedule launch</strong> for a future time, and set <strong>Send by</strong> to drip emails evenly
          across a window instead of all at once.</li>
        <li>Watch results live on the campaign page (funnel + per-recipient timeline). <strong>Export CSV</strong> anytime.</li>
      </ul>

      <h2 id="tracking">7. How tracking works</h2>
      <ul>
        <li><strong>Opened</strong> — a 1×1 transparent pixel is embedded in the HTML. When the recipient's mail
          client loads images, the open is recorded.</li>
        <li><strong>Clicked</strong> — links go through <code>/c/&lt;rid&gt;</code>, which records the click then redirects.</li>
        <li><strong>Submitted</strong> — a landing-page form post is recorded (password discarded).</li>
        <li><strong>Reported</strong> — <code>/report?rid=&lt;rid&gt;</code> marks a recipient as having reported the phish
          (wire it to a mail-client "report" button).</li>
      </ul>
      <p className="hint">
        Note: many mail clients block or proxy remote images by default (Gmail, Outlook, Apple Mail Privacy
        Protection). If images are blocked, an open won't register until the recipient loads images — this is a
        limitation of email itself, not VoltPhish. A <em>click</em> always implies an open, so click-through is the
        most reliable engagement signal.
      </p>

      <h2 id="webhooks">8. Webhooks (admin)</h2>
      <p>
        POST campaign events to an external system. Every delivery is <strong>HMAC-SHA256 signed</strong> in the
        <code>X-VoltPhish-Signature</code> header; verify it with your webhook secret. Delivery is retried via the
        durable job queue, and target URLs are SSRF-guarded.
      </p>

      <h2 id="api">9. REST API keys</h2>
      <p>Create a key under <strong>API Keys</strong>, then call any endpoint with a bearer token:</p>
      <pre>{`curl -H "Authorization: Bearer psk_xxx" \\
     https://your-host/api/v1/campaigns`}</pre>
      <p className="hint">Interactive API reference (dev mode): <code>/api/docs</code>.</p>
    </div>
  );
}
