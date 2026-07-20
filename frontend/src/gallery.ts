// Ready-made simulation content. All use {{.FirstName}} / {{.URL}} tokens.
// Styling is generic (no real logos) — appropriate for awareness training.

export interface GalleryTemplate {
  name: string;
  category: string;
  subject: string;
  html: string;
  text: string;
}

export interface GalleryPage {
  name: string;
  category: string;
  html: string;
}

const wrap = (inner: string) =>
  `<div style="font-family:Segoe UI,Arial,sans-serif;max-width:600px;margin:0 auto;color:#1a1a1a;font-size:15px;line-height:1.55">${inner}</div>`;

const btn = (label: string) =>
  `<a href="{{.URL}}" style="display:inline-block;background:#0067b8;color:#fff;text-decoration:none;padding:12px 26px;border-radius:5px;font-weight:600">${label}</a>`;

const btnC = (label: string, color: string) =>
  `<a href="{{.URL}}" style="display:inline-block;background:${color};color:#fff;text-decoration:none;padding:12px 26px;border-radius:5px;font-weight:600">${label}</a>`;

export const GALLERY_TEMPLATES: GalleryTemplate[] = [
  {
    name: "IT — Password expiry",
    category: "IT Helpdesk",
    subject: "Action required: your password expires today",
    text: "Hi {{.FirstName}}, your password expires today. Reset it here: {{.URL}}",
    html: wrap(`
      <p>Hi {{.FirstName}},</p>
      <p>Our records show that your corporate password <strong>expires today</strong>. To avoid losing access to email and internal systems, please reset it now.</p>
      <p style="margin:26px 0">${btn("Reset my password")}</p>
      <p style="color:#666;font-size:13px">If you do not reset your password, your account may be temporarily suspended.</p>
      <p>— IT Service Desk</p>`),
  },
  {
    name: "Microsoft 365 — Unusual sign-in",
    category: "Microsoft 365",
    subject: "Unusual sign-in activity on your Microsoft account",
    text: "Hi {{.FirstName}}, we detected an unusual sign-in. Review activity: {{.URL}}",
    html: wrap(`
      <p style="font-size:20px;font-weight:600;color:#0067b8">Microsoft account</p>
      <p>Hi {{.FirstName}},</p>
      <p>We detected an <strong>unusual sign-in</strong> to your Microsoft 365 account from a new device. If this wasn't you, secure your account immediately.</p>
      <table style="margin:14px 0;font-size:14px;color:#444"><tr><td>Location</td><td style="padding-left:20px">Kyiv, Ukraine</td></tr><tr><td>Device</td><td style="padding-left:20px">Windows · Chrome</td></tr></table>
      <p style="margin:26px 0">${btn("Review activity")}</p>
      <p style="color:#666;font-size:13px">The Microsoft account team</p>`),
  },
  {
    name: "Google — Security alert",
    category: "Google",
    subject: "Security alert: new device signed in",
    text: "Hi {{.FirstName}}, a new device signed in to your Google account. Check: {{.URL}}",
    html: wrap(`
      <p style="font-size:20px;font-weight:500">Google</p>
      <hr style="border:none;border-top:1px solid #eee">
      <p style="font-size:17px;font-weight:500">A new device signed in to your account</p>
      <p>Hi {{.FirstName}}, your Google Account was just signed in to from a new Windows device. You're getting this email to make sure it was you.</p>
      <p style="margin:26px 0"><a href="{{.URL}}" style="display:inline-block;border:1px solid #1a73e8;color:#1a73e8;text-decoration:none;padding:10px 24px;border-radius:4px;font-weight:600">Check activity</a></p>`),
  },
  {
    name: "HR — Payroll revision",
    category: "HR / Finance",
    subject: "Your 2026 salary revision letter is ready",
    text: "Hi {{.FirstName}}, your salary revision letter is ready. View: {{.URL}}",
    html: wrap(`
      <p>Dear {{.FirstName}},</p>
      <p>The annual compensation review has been completed. Your <strong>2026 salary revision letter</strong> is now available in the HR portal. Please review and acknowledge it before the end of this week.</p>
      <p style="margin:26px 0">${btn("View my letter")}</p>
      <p>Regards,<br>Human Resources</p>`),
  },
  {
    name: "Courier — Delivery on hold",
    category: "Delivery",
    subject: "Your parcel is on hold — action needed",
    text: "Hi {{.FirstName}}, your parcel is on hold. Confirm details: {{.URL}}",
    html: wrap(`
      <p>Hi {{.FirstName}},</p>
      <p>We attempted to deliver your parcel but it is currently <strong>on hold</strong> because the delivery address could not be confirmed. Please verify your details to reschedule delivery.</p>
      <p style="margin:26px 0">${btn("Confirm & reschedule")}</p>
      <p style="color:#666;font-size:13px">Tracking ID: 7731-XA-2290</p>`),
  },
  {
    name: "IT — MFA re-enrollment",
    category: "IT Helpdesk",
    subject: "Re-enroll your multi-factor authentication",
    text: "Hi {{.FirstName}}, MFA re-enrollment is required. Start: {{.URL}}",
    html: wrap(`
      <p>Hi {{.FirstName}},</p>
      <p>As part of a security upgrade, all employees must <strong>re-enroll their multi-factor authentication (MFA)</strong> device by Friday. Accounts that are not re-enrolled will be locked.</p>
      <p style="margin:26px 0">${btn("Re-enroll now")}</p>
      <p>— Information Security Team</p>`),
  },
  {
    name: "Quishing — Scan to verify MFA (QR)",
    category: "QR / Quishing",
    subject: "Scan the QR code to keep your account active",
    text: "Hi {{.FirstName}}, scan the QR in this email — or use this link — to re-verify your account: {{.URL}}",
    html: wrap(`
      <p style="font-size:20px;font-weight:600;color:#0067b8">Account verification required</p>
      <p>Hi {{.FirstName}},</p>
      <p>Our new authentication system requires all employees to <strong>re-verify their account by scanning the QR code below</strong> with a mobile device. This must be completed within 24 hours to avoid a temporary suspension.</p>
      <div style="text-align:center;margin:28px 0">
        {{.QR}}
        <div style="color:#666;font-size:13px;margin-top:10px">Open your phone camera and point it at the code</div>
      </div>
      <p style="color:#666;font-size:13px">Can't scan? <a href="{{.URL}}" style="color:#0067b8">Verify here instead</a>.</p>
      <p>— IT Security</p>`),
  },
  {
    name: "Microsoft Teams — Message waiting",
    category: "Microsoft 365",
    subject: "You have 3 unread messages in Teams",
    text: "Hi {{.FirstName}}, you have unread Teams messages. View: {{.URL}}",
    html: wrap(`
      <div style="background:#4b53bc;color:#fff;padding:16px 20px;font-size:18px;font-weight:600;border-radius:6px 6px 0 0">Microsoft Teams</div>
      <div style="border:1px solid #eee;border-top:none;padding:24px 22px;border-radius:0 0 6px 6px">
        <p>Hi {{.FirstName}},</p>
        <p>You have <strong>3 unread messages</strong> and 1 missed call in Microsoft Teams. Your teammates are waiting for a reply.</p>
        <div style="background:#f5f6fb;border-left:3px solid #4b53bc;padding:12px 14px;margin:16px 0;font-size:14px;color:#444">
          <strong>Priya (Manager):</strong> "Can you review this before the standup?"
        </div>
        <p style="margin:24px 0">${btnC("Reply in Teams", "#4b53bc")}</p>
      </div>`),
  },
  {
    name: "SharePoint — File shared with you",
    category: "Microsoft 365",
    subject: "A document has been shared with you",
    text: "Hi {{.FirstName}}, a file was shared with you. Open: {{.URL}}",
    html: wrap(`
      <p>Hi {{.FirstName}},</p>
      <p>A colleague has shared a document with you on SharePoint.</p>
      <div style="border:1px solid #e5e5e5;border-radius:8px;padding:16px 18px;margin:18px 0;display:flex;align-items:center;gap:14px">
        <div style="font-size:34px">📄</div>
        <div>
          <div style="font-weight:600">Q3-Budget-Review-CONFIDENTIAL.xlsx</div>
          <div style="color:#888;font-size:13px">Shared by finance@ · Modified 2 hours ago</div>
        </div>
      </div>
      <p style="margin:24px 0">${btn("Open document")}</p>
      <p style="color:#666;font-size:13px">This link will work for 7 days.</p>`),
  },
  {
    name: "OneDrive — Storage almost full",
    category: "Microsoft 365",
    subject: "Your OneDrive is 98% full — files may stop syncing",
    text: "Hi {{.FirstName}}, your OneDrive is almost full. Free up space: {{.URL}}",
    html: wrap(`
      <p>Hi {{.FirstName}},</p>
      <p>Your OneDrive is <strong>98% full</strong>. Once you reach your limit, new files won't sync and you may not be able to receive shared files.</p>
      <div style="background:#eee;border-radius:10px;height:12px;margin:16px 0;overflow:hidden"><div style="width:98%;height:100%;background:#d13438"></div></div>
      <p style="margin:24px 0">${btn("Manage storage")}</p>
      <p>— Microsoft OneDrive</p>`),
  },
  {
    name: "DocuSign — Awaiting your signature",
    category: "e-Signature",
    subject: "Please DocuSign: Employment Agreement Amendment",
    text: "Hi {{.FirstName}}, a document is awaiting your signature. Review: {{.URL}}",
    html: wrap(`
      <div style="background:#ffce00;padding:14px 20px;font-weight:700;color:#000;border-radius:6px 6px 0 0">DocuSign</div>
      <div style="border:1px solid #eee;border-top:none;padding:24px 22px">
        <p>Hi {{.FirstName}},</p>
        <p><strong>Human Resources</strong> has sent you a document to review and sign:</p>
        <p style="font-size:16px;font-weight:600;margin:14px 0">"Employment Agreement Amendment 2026"</p>
        <p style="margin:24px 0">${btnC("Review & sign", "#e8a800")}</p>
        <p style="color:#888;font-size:12px">Do not share this email. This link is unique to you.</p>
      </div>`),
  },
  {
    name: "Finance — Invoice approval required",
    category: "HR / Finance",
    subject: "Invoice #INV-88213 requires your approval",
    text: "Hi {{.FirstName}}, invoice INV-88213 needs your approval: {{.URL}}",
    html: wrap(`
      <p>Hi {{.FirstName}},</p>
      <p>An invoice assigned to your cost center is <strong>pending approval</strong> and is now overdue. Please review and approve it to avoid a late-payment penalty.</p>
      <table style="width:100%;font-size:14px;border-collapse:collapse;margin:14px 0">
        <tr><td style="padding:6px 0;color:#888">Vendor</td><td style="text-align:right">Britewave Solutions</td></tr>
        <tr><td style="padding:6px 0;color:#888">Amount</td><td style="text-align:right;font-weight:600">₹2,84,500</td></tr>
        <tr><td style="padding:6px 0;color:#888">Due</td><td style="text-align:right;color:#d13438">Overdue by 2 days</td></tr>
      </table>
      <p style="margin:24px 0">${btnC("Review & approve", "#107c41")}</p>
      <p>— Accounts Payable</p>`),
  },
  {
    name: "HR — Policy update (acknowledge)",
    category: "HR / Finance",
    subject: "Action required: acknowledge the updated Code of Conduct",
    text: "Hi {{.FirstName}}, please acknowledge the updated policy: {{.URL}}",
    html: wrap(`
      <p>Dear {{.FirstName}},</p>
      <p>We have updated our <strong>Code of Conduct and Remote Work Policy</strong>, effective immediately. All employees are required to read and acknowledge the new policy <strong>by end of day Friday</strong>.</p>
      <p>Failure to acknowledge may affect your compliance status.</p>
      <p style="margin:24px 0">${btn("Read & acknowledge")}</p>
      <p>Thank you,<br>Human Resources</p>`),
  },
  {
    name: "CEO — Quick request (BEC)",
    category: "Executive / BEC",
    subject: "Quick favor — are you available?",
    text: "Hi {{.FirstName}}, are you at your desk? I need you to handle something quickly. {{.URL}}",
    html: wrap(`
      <p>{{.FirstName}},</p>
      <p>Are you available right now? I'm going into back-to-back meetings and need you to take care of something time-sensitive for me. It's a bit urgent — let me know as soon as you see this.</p>
      <p style="margin:22px 0">${btnC("Yes, I can help", "#333")}</p>
      <p style="color:#888;font-size:13px">Sent from my iPhone</p>`),
  },
  {
    name: "IT — VPN client must be updated",
    category: "IT Helpdesk",
    subject: "Mandatory VPN update before Monday",
    text: "Hi {{.FirstName}}, update your VPN client before Monday: {{.URL}}",
    html: wrap(`
      <p>Hi {{.FirstName}},</p>
      <p>Due to a security patch, all employees must update their <strong>VPN client</strong> before Monday 9:00 AM. Devices running the old version will lose remote access to internal systems.</p>
      <p style="margin:24px 0">${btn("Update VPN client")}</p>
      <p>— IT Infrastructure</p>`),
  },
  {
    name: "LinkedIn — New messages & requests",
    category: "Social",
    subject: "You have 5 new notifications",
    text: "Hi {{.FirstName}}, you have new LinkedIn notifications: {{.URL}}",
    html: wrap(`
      <div style="background:#0a66c2;color:#fff;padding:14px 20px;font-size:18px;font-weight:700;border-radius:6px 6px 0 0">in</div>
      <div style="border:1px solid #eee;border-top:none;padding:22px">
        <p>Hi {{.FirstName}},</p>
        <p>You have <strong>2 new connection requests</strong> and <strong>3 unread messages</strong>, including one from a recruiter.</p>
        <p style="margin:22px 0">${btnC("View on LinkedIn", "#0a66c2")}</p>
      </div>`),
  },
  {
    name: "Zoom — Missed meeting recording",
    category: "Social",
    subject: "Your meeting recording is ready to view",
    text: "Hi {{.FirstName}}, your Zoom recording is ready: {{.URL}}",
    html: wrap(`
      <div style="background:#2d8cff;color:#fff;padding:14px 20px;font-size:18px;font-weight:600;border-radius:6px 6px 0 0">Zoom</div>
      <div style="border:1px solid #eee;border-top:none;padding:22px">
        <p>Hi {{.FirstName}},</p>
        <p>The recording of <strong>"All-Hands Q3 Review"</strong> is now available. You were marked as absent — please review the recording.</p>
        <p style="margin:22px 0">${btnC("View recording", "#2d8cff")}</p>
      </div>`),
  },
  {
    name: "Benefits — Enrollment closing",
    category: "HR / Finance",
    subject: "Last day to confirm your 2026 health benefits",
    text: "Hi {{.FirstName}}, benefits enrollment closes today. Confirm: {{.URL}}",
    html: wrap(`
      <p>Dear {{.FirstName}},</p>
      <p>Open enrollment for your <strong>2026 health and insurance benefits closes today</strong>. If you do not confirm your selections, you will be assigned the default plan for the year.</p>
      <p style="margin:24px 0">${btnC("Confirm my benefits", "#107c41")}</p>
      <p>— People &amp; Culture</p>`),
  },
  {
    name: "Voicemail — New message",
    category: "IT Helpdesk",
    subject: "You have a new voicemail (0:42)",
    text: "Hi {{.FirstName}}, you have a new voicemail. Listen: {{.URL}}",
    html: wrap(`
      <p>Hi {{.FirstName}},</p>
      <p>You received a new voicemail on your business line.</p>
      <div style="border:1px solid #e5e5e5;border-radius:8px;padding:16px 18px;margin:18px 0;display:flex;align-items:center;gap:14px">
        <div style="font-size:30px">🎙️</div>
        <div><div style="font-weight:600">Voicemail · 0:42</div><div style="color:#888;font-size:13px">From +91 22 4890 ···· · Today</div></div>
      </div>
      <p style="margin:22px 0">${btn("Listen to message")}</p>
      <p>— Unified Messaging</p>`),
  },
];

const pageWrap = (title: string, inner: string) =>
  `<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${title}</title></head>
<body style="font-family:Segoe UI,Arial,sans-serif;background:#f3f3f3;margin:0">
<div style="max-width:380px;margin:8vh auto;background:#fff;padding:36px;border-radius:8px;box-shadow:0 2px 14px rgba(0,0,0,0.08)">${inner}</div>
</body></html>`;

const loginForm = (heading: string, brandColor: string) =>
  pageWrap(
    heading,
    `<h1 style="font-size:20px;color:${brandColor};margin:0 0 6px">${heading}</h1>
     <p style="color:#666;font-size:14px;margin:0 0 22px">Sign in to continue</p>
     <form method="post">
       <label style="font-size:13px;color:#333">Email or username</label>
       <input name="username" type="text" style="width:100%;padding:10px;margin:6px 0 16px;border:1px solid #ccc;border-radius:4px;box-sizing:border-box">
       <label style="font-size:13px;color:#333">Password</label>
       <input name="password" type="password" style="width:100%;padding:10px;margin:6px 0 22px;border:1px solid #ccc;border-radius:4px;box-sizing:border-box">
       <button type="submit" style="width:100%;background:${brandColor};color:#fff;border:none;padding:12px;border-radius:4px;font-weight:600;cursor:pointer">Sign in</button>
     </form>`,
  );

// A fake "Verify you are human" (ClickFix-style) page. Pure HTML/CSS so it works
// under the strict landing-page CSP (no inline JS). Clicking the verify widget is
// a <button type=submit>, so the click is recorded as engagement (the fail) and
// the recipient is redirected to the teaching page. NO real command is ever
// shown or run — we only measure who would fall for the lure.
const clickfixPage = `<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Verify you are human</title></head>
<body style="font-family:Segoe UI,Arial,sans-serif;background:#f5f5f7;margin:0;color:#1a1a1a">
<div style="max-width:520px;margin:12vh auto;text-align:center;padding:0 20px">
  <h1 style="font-size:22px;font-weight:600;margin:0 0 8px">Verify you are human</h1>
  <p style="color:#555;font-size:14px;margin:0 0 28px">Complete the action below to confirm you're not a bot and continue to the document.</p>
  <form method="post">
    <button type="submit" name="verify" value="1" style="display:flex;align-items:center;gap:14px;width:300px;margin:0 auto;background:#fff;border:1px solid #d0d0d5;border-radius:8px;padding:16px 18px;cursor:pointer;box-shadow:0 1px 4px rgba(0,0,0,0.06)">
      <span style="width:26px;height:26px;border:2px solid #b8b8bf;border-radius:5px;flex:none"></span>
      <span style="font-size:15px;color:#222">Verify you are human</span>
      <span style="margin-left:auto;text-align:right;line-height:1.1"><span style="font-size:13px;font-weight:700;color:#f38020">CF</span><br><span style="font-size:9px;color:#999">Privacy · Terms</span></span>
    </button>
  </form>
  <p style="color:#999;font-size:12px;margin-top:26px">This check is taking a moment to verify your browser…</p>
</div>
</body></html>`;

// A "Browser-in-the-Browser" (BitB) page: a fake browser popup window — complete
// with a title bar and a spoofed address bar — rendered INSIDE the real page, so
// the URL bar the victim trusts is actually fake. Contains a Microsoft login
// form (submissions captured; password never stored). Pure HTML/CSS.
const bitbPage = `<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Sign in to your account</title></head>
<body style="font-family:Segoe UI,Arial,sans-serif;margin:0;background:linear-gradient(135deg,#e8eef7,#dfe7f2);min-height:100vh">
<div style="max-width:500px;margin:9vh auto;border-radius:8px;overflow:hidden;box-shadow:0 18px 50px rgba(0,0,0,0.28);border:1px solid #cfd6e0">
  <div style="background:#e6e9ee;padding:8px 12px;display:flex;align-items:center;gap:8px;border-bottom:1px solid #d3d7de">
    <span style="width:12px;height:12px;border-radius:50%;background:#ff5f57;display:inline-block"></span>
    <span style="width:12px;height:12px;border-radius:50%;background:#febc2e;display:inline-block"></span>
    <span style="width:12px;height:12px;border-radius:50%;background:#28c840;display:inline-block"></span>
    <div style="flex:1;margin-left:10px;background:#fff;border:1px solid #d3d7de;border-radius:14px;padding:5px 12px;font-size:12px;color:#333;display:flex;align-items:center;gap:6px">
      <span style="color:#2ba640">🔒</span><span>https://login.microsoftonline.com/common/oauth2/authorize</span>
    </div>
  </div>
  <div style="background:#fff;padding:44px 40px">
    <div style="font-size:21px;font-weight:600;color:#0067b8;margin:0 0 4px">Microsoft</div>
    <p style="font-size:15px;margin:18px 0 20px">Sign in to continue to Outlook</p>
    <form method="post">
      <input name="username" type="email" placeholder="Email, phone, or Skype" style="width:100%;padding:10px 4px;margin:0 0 18px;border:none;border-bottom:1px solid #666;box-sizing:border-box;font-size:15px">
      <input name="password" type="password" placeholder="Password" style="width:100%;padding:10px 4px;margin:0 0 24px;border:none;border-bottom:1px solid #666;box-sizing:border-box;font-size:15px">
      <div style="text-align:right"><button type="submit" style="background:#0067b8;color:#fff;border:none;padding:9px 34px;font-size:15px;cursor:pointer">Sign in</button></div>
    </form>
  </div>
</div>
</body></html>`;

const input = (label: string, name: string, type = "text") =>
  `<label style="font-size:13px;color:#333">${label}</label>
   <input name="${name}" type="${type}" style="width:100%;padding:10px;margin:6px 0 16px;border:1px solid #ccc;border-radius:4px;box-sizing:border-box">`;

const submitBtn = (label: string, color: string) =>
  `<button type="submit" style="width:100%;background:${color};color:#fff;border:none;padding:12px;border-radius:4px;font-weight:600;cursor:pointer">${label}</button>`;

// A file-share page (SharePoint/OneDrive-style) that requires sign-in to view.
const fileDownloadPage = pageWrap(
  "Shared document",
  `<div style="text-align:center;margin-bottom:20px">
     <div style="font-size:40px">📄</div>
     <div style="font-weight:600;margin-top:6px">Q3-Budget-Review-CONFIDENTIAL.xlsx</div>
     <div style="color:#888;font-size:13px">2.4 MB · Protected document</div>
   </div>
   <p style="font-size:13px;color:#555;text-align:center;margin:0 0 18px">Sign in with your work account to view this file.</p>
   <form method="post">
     ${input("Work email", "username", "email")}
     ${input("Password", "password", "password")}
     ${submitBtn("Sign in to view", "#0067b8")}
   </form>`,
);

// A "verify with your 6-digit code" MFA-capture page.
const mfaCodePage = pageWrap(
  "Verify it's you",
  `<h1 style="font-size:19px;margin:0 0 8px">Enter your verification code</h1>
   <p style="color:#666;font-size:14px;margin:0 0 20px">We sent a 6-digit code to your device. Enter it below to confirm your identity.</p>
   <form method="post">
     <input name="code" inputmode="numeric" maxlength="6" placeholder="••••••" style="width:100%;text-align:center;letter-spacing:10px;font-size:24px;padding:12px;margin:0 0 18px;border:1px solid #ccc;border-radius:6px;box-sizing:border-box">
     ${submitBtn("Verify", "#0067b8")}
   </form>
   <p style="text-align:center;font-size:12px;color:#999;margin-top:14px">Didn't get a code? Resend</p>`,
);

// An employee-survey lure form (with a "reward" hook).
const surveyPage = pageWrap(
  "Employee survey",
  `<h1 style="font-size:19px;margin:0 0 6px">2026 Employee Engagement Survey</h1>
   <p style="color:#666;font-size:13px;margin:0 0 18px">Complete this 1-minute survey to claim your ₹500 voucher. Sign in to begin.</p>
   <form method="post">
     ${input("Work email", "username", "email")}
     ${input("Password", "password", "password")}
     <label style="font-size:13px;color:#333">How satisfied are you at work?</label>
     <select name="q1" style="width:100%;padding:10px;margin:6px 0 16px;border:1px solid #ccc;border-radius:4px;box-sizing:border-box">
       <option>Very satisfied</option><option>Satisfied</option><option>Neutral</option><option>Unsatisfied</option>
     </select>
     ${submitBtn("Submit & claim voucher", "#6b21a8")}
   </form>`,
);

// A delivery "confirm & reschedule" form (no card fields — address confirmation).
const deliveryPage = pageWrap(
  "Reschedule delivery",
  `<h1 style="font-size:19px;margin:0 0 6px">Confirm your delivery details</h1>
   <p style="color:#666;font-size:13px;margin:0 0 18px">Tracking 7731-XA-2290 · Your parcel is on hold. Confirm your details to reschedule.</p>
   <form method="post">
     ${input("Full name", "fullname")}
     ${input("Delivery address", "address")}
     ${input("Mobile number", "phone", "tel")}
     ${submitBtn("Confirm & reschedule", "#b45309")}
   </form>`,
);

// A DocuSign-style review-and-sign page.
const docusignPage = `<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Review &amp; sign</title></head>
<body style="font-family:Segoe UI,Arial,sans-serif;background:#f3f3f3;margin:0">
  <div style="background:#ffce00;padding:12px 20px;font-weight:700;color:#000">DocuSign</div>
  <div style="max-width:420px;margin:6vh auto;background:#fff;padding:34px;border-radius:8px;box-shadow:0 2px 14px rgba(0,0,0,0.08)">
    <div style="font-size:34px;text-align:center">📑</div>
    <h1 style="font-size:18px;text-align:center;margin:8px 0 4px">Employment Agreement Amendment</h1>
    <p style="color:#666;font-size:13px;text-align:center;margin:0 0 20px">Sign in to review and electronically sign this document.</p>
    <form method="post">
      ${input("Email", "username", "email")}
      ${input("Password", "password", "password")}
      ${submitBtn("Review document", "#e8a800")}
    </form>
  </div>
</body></html>`;

export const GALLERY_PAGES: GalleryPage[] = [
  { name: "ClickFix — Verify you are human", category: "QR / Modern", html: clickfixPage },
  { name: "Browser-in-the-Browser (MS login)", category: "QR / Modern", html: bitbPage },
  { name: "Verification code (MFA capture)", category: "QR / Modern", html: mfaCodePage },
  { name: "Microsoft 365 login", category: "Microsoft 365", html: loginForm("Sign in to Microsoft 365", "#0067b8") },
  { name: "Outlook Web App login", category: "Microsoft 365", html: loginForm("Outlook Web App", "#0067b8") },
  { name: "SharePoint file download", category: "Microsoft 365", html: fileDownloadPage },
  { name: "Google login", category: "Google", html: loginForm("Sign in with Google", "#1a73e8") },
  { name: "LinkedIn login", category: "Social", html: loginForm("Sign in to LinkedIn", "#0a66c2") },
  { name: "Zoom login", category: "Social", html: loginForm("Sign in to Zoom", "#2d8cff") },
  { name: "DocuSign — review & sign", category: "e-Signature", html: docusignPage },
  { name: "Company SSO portal", category: "Generic", html: loginForm("Company Single Sign-On", "#2d3748") },
  { name: "VPN portal login", category: "IT Helpdesk", html: loginForm("Secure VPN Portal", "#107c41") },
  { name: "Webmail login", category: "IT Helpdesk", html: loginForm("Webmail", "#374151") },
  { name: "HR self-service portal", category: "HR / Finance", html: loginForm("HR Self-Service Portal", "#6b21a8") },
  { name: "Payroll portal login", category: "HR / Finance", html: loginForm("Payroll Portal", "#b45309") },
  { name: "Employee survey (reward)", category: "HR / Finance", html: surveyPage },
  { name: "Delivery reschedule form", category: "Delivery", html: deliveryPage },
  {
    name: "Password reset form",
    category: "IT Helpdesk",
    html: pageWrap(
      "Reset password",
      `<h1 style="font-size:19px;margin:0 0 18px">Reset your password</h1>
       <form method="post">
         <label style="font-size:13px">Corporate email</label>
         <input name="username" type="email" style="width:100%;padding:10px;margin:6px 0 16px;border:1px solid #ccc;border-radius:4px;box-sizing:border-box">
         <label style="font-size:13px">New password</label>
         <input name="password" type="password" style="width:100%;padding:10px;margin:6px 0 22px;border:1px solid #ccc;border-radius:4px;box-sizing:border-box">
         <button type="submit" style="width:100%;background:#0067b8;color:#fff;border:none;padding:12px;border-radius:4px;font-weight:600;cursor:pointer">Update password</button>
       </form>`,
    ),
  },
];
