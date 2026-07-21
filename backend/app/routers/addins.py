"""Serve the Report-Phish add-ins (Outlook manifest + task pane, Gmail script).

These are PUBLIC routes — a mail client (Outlook desktop/web, Gmail) fetches them,
so they can't sit behind the session cookie. The task pane still needs the report
token to call the ingest endpoint; since the add-in is deployed inside the org's
own authenticated mail client to internal users, the token is injected into the
page here. It gates only report ingestion (never account access) and is
regenerable by an admin. Nothing else sensitive is exposed.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session as DbSession

from ..database import get_db
from ..services.report_token import get_or_create_report_token

router = APIRouter(prefix="/addins", tags=["addins"])

# Stable add-in identity (a fixed GUID keeps re-deploys upgrading in place).
_ADDIN_ID = "b9f3a1c2-4d5e-6f70-8a90-1b2c3d4e5f60"


def _base(request: Request) -> str:
    return str(request.base_url).rstrip("/")


@router.get("/outlook/manifest.xml")
def outlook_manifest(request: Request) -> Response:
    b = _base(request)
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<OfficeApp xmlns="http://schemas.microsoft.com/office/appforoffice/1.1"
           xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
           xmlns:bt="http://schemas.microsoft.com/office/officeappbasictypes/1.0"
           xmlns:mailappor="http://schemas.microsoft.com/office/mailappversionoverrides/1.0"
           xsi:type="MailApp">
  <Id>{_ADDIN_ID}</Id>
  <Version>1.0.0</Version>
  <ProviderName>VoltPhish</ProviderName>
  <DefaultLocale>en-US</DefaultLocale>
  <DisplayName DefaultValue="Report Phish" />
  <Description DefaultValue="Report a suspicious email to your security team in one click." />
  <IconUrl DefaultValue="{b}/logo.png" />
  <HighResolutionIconUrl DefaultValue="{b}/logo.png" />
  <SupportUrl DefaultValue="{b}/" />
  <Hosts>
    <Host Name="Mailbox" />
  </Hosts>
  <Requirements>
    <Sets>
      <Set Name="Mailbox" MinVersion="1.3" />
    </Sets>
  </Requirements>
  <FormSettings>
    <Form xsi:type="ItemRead">
      <DesktopSettings>
        <SourceLocation DefaultValue="{b}/addins/outlook/taskpane.html" />
        <RequestedHeight>250</RequestedHeight>
      </DesktopSettings>
    </Form>
  </FormSettings>
  <Permissions>ReadItem</Permissions>
  <Rule xsi:type="RuleCollection" Mode="Or">
    <Rule xsi:type="ItemIs" ItemType="Message" FormType="Read" />
  </Rule>
</OfficeApp>
"""
    return Response(content=xml, media_type="application/xml")


@router.get("/outlook/taskpane.html")
def outlook_taskpane(request: Request, db: DbSession = Depends(get_db)) -> Response:
    b = _base(request)
    token = get_or_create_report_token(db)
    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Report Phish</title>
<script src="https://appsforoffice.microsoft.com/lib/1/hosted/office.js"></script>
<style>
  body {{ font-family: "Segoe UI", system-ui, sans-serif; margin: 0; padding: 16px; color: #1e293b; }}
  .brand {{ display:flex; align-items:center; gap:8px; margin-bottom:12px; }}
  .brand img {{ height:24px; }}
  h1 {{ font-size:15px; margin:0; }}
  p {{ font-size:13px; color:#475569; line-height:1.4; }}
  button {{ width:100%; padding:10px 14px; border:0; border-radius:8px; background:#4f46e5;
           color:#fff; font-size:14px; font-weight:600; cursor:pointer; }}
  button:disabled {{ opacity:.6; cursor:default; }}
  .msg {{ margin-top:12px; padding:10px 12px; border-radius:8px; font-size:13px; display:none; }}
  .ok {{ background:#dcfce7; color:#166534; }}
  .warn {{ background:#fef9c3; color:#854d0e; }}
  .err {{ background:#fee2e2; color:#991b1b; }}
</style>
</head>
<body>
  <div class="brand"><img src="{b}/logo.png" alt="" /><h1>Report Phish</h1></div>
  <p>Think this email is suspicious? Report it to your security team. If it's a
     training test, you'll be credited for catching it.</p>
  <button id="btn">Report this email</button>
  <div class="msg" id="msg"></div>
<script>
  window.__API = "{b}";
  window.__TOKEN = "{token}";
</script>
<script src="{b}/addins/outlook/taskpane.js"></script>
</body>
</html>
"""
    resp = Response(content=html, media_type="text/html")
    # Allow Office.js from the Microsoft CDN and framing inside Outlook clients.
    resp.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' https://appsforoffice.microsoft.com 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; "
        "connect-src 'self'; "
        "frame-ancestors https://outlook.office.com https://outlook.office365.com "
        "https://outlook.live.com 'self'"
    )
    resp.headers["X-Frame-Options"] = "ALLOW-FROM https://outlook.office.com"
    return resp


@router.get("/outlook/taskpane.js")
def outlook_taskpane_js(request: Request) -> Response:
    js = r"""
(function () {
  var btn = document.getElementById("btn");
  var msg = document.getElementById("msg");
  function show(cls, text) { msg.className = "msg " + cls; msg.style.display = "block"; msg.textContent = text; }

  function post(payload) {
    return fetch(window.__API + "/api/v1/inbound/report", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Report-Token": window.__TOKEN },
      body: JSON.stringify(payload)
    }).then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); });
  }

  function gatherAndSend() {
    btn.disabled = true;
    show("warn", "Reporting…");
    try {
      var item = Office.context.mailbox.item;
      var reporter = "";
      try { reporter = Office.context.mailbox.userProfile.emailAddress || ""; } catch (e) {}
      var sender = "";
      try { sender = (item.from && (item.from.emailAddress || item.from.displayName)) || ""; } catch (e) {}
      var subject = item.subject || "";
      item.body.getAsync(Office.CoercionType.Text, function (res) {
        var body = (res && res.status === "succeeded") ? (res.value || "") : "";
        post({ reporter_email: reporter, subject: subject, sender: sender, body: body })
          .then(function (r) {
            if (r.ok) { show(r.d.simulation ? "ok" : "ok", r.d.detail); }
            else { show("err", (r.d && r.d.detail) || "Couldn't report this message."); btn.disabled = false; }
          })
          .catch(function () { show("err", "Network error — please try again."); btn.disabled = false; });
      });
    } catch (e) {
      show("err", "Add-in error — please try again.");
      btn.disabled = false;
    }
  }

  Office.onReady(function () { btn.addEventListener("click", gatherAndSend); });
})();
"""
    return Response(content=js, media_type="application/javascript")


@router.get("/gmail/Code.gs")
def gmail_script(request: Request, db: DbSession = Depends(get_db)) -> Response:
    b = _base(request)
    token = get_or_create_report_token(db)
    gs = f"""/**
 * VoltPhish — Report Phish (Gmail add-in / Google Apps Script).
 *
 * Deploy: script.google.com → new project → paste this file → add the Gmail
 * add-in manifest (see appsscript.json at {b}/addins/gmail/appsscript.json) →
 * Deploy > Test deployments > install. A "Report Phish" card appears on open.
 */
var API = "{b}";
var TOKEN = "{token}";

function onGmailMessageOpen(e) {{
  var card = CardService.newCardBuilder()
    .setHeader(CardService.newCardHeader().setTitle("Report Phish"))
    .addSection(CardService.newCardSection()
      .addWidget(CardService.newTextParagraph().setText(
        "Suspicious email? Report it to your security team. If it's a training test, you'll be credited for catching it."))
      .addWidget(CardService.newTextButton()
        .setText("Report this email")
        .setOnClickAction(CardService.newAction().setFunctionName("reportPhish"))))
    .build();
  return [card];
}}

function reportPhish(e) {{
  var accessToken = e.gmail.accessToken;
  var messageId = e.gmail.messageId;
  GmailApp.setCurrentMessageAccessToken(accessToken);
  var msg = GmailApp.getMessageById(messageId);

  var payload = {{
    reporter_email: Session.getActiveUser().getEmail(),
    subject: msg.getSubject(),
    sender: msg.getFrom(),
    body: msg.getPlainBody(),
    headers: msg.getRawContent().slice(0, 4000)
  }};

  var resp = UrlFetchApp.fetch(API + "/api/v1/inbound/report", {{
    method: "post",
    contentType: "application/json",
    headers: {{ "X-Report-Token": TOKEN }},
    payload: JSON.stringify(payload),
    muteHttpExceptions: true
  }});

  var detail = "Reported to your security team.";
  try {{ detail = JSON.parse(resp.getContentText()).detail || detail; }} catch (err) {{}}
  return CardService.newActionResponseBuilder()
    .setNotification(CardService.newNotification().setText(detail))
    .build();
}}
"""
    return Response(content=gs, media_type="text/plain")


@router.get("/gmail/appsscript.json")
def gmail_manifest(request: Request) -> Response:
    b = _base(request)
    manifest = f"""{{
  "timeZone": "Etc/UTC",
  "oauthScopes": [
    "https://www.googleapis.com/auth/gmail.addons.current.message.readonly",
    "https://www.googleapis.com/auth/gmail.addons.execute",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/script.external_request"
  ],
  "gmail": {{
    "name": "Report Phish",
    "logoUrl": "{b}/logo.png",
    "contextualTriggers": [{{
      "unconditional": {{}},
      "onTriggerFunction": "onGmailMessageOpen"
    }}],
    "primaryColor": "#4f46e5",
    "secondaryColor": "#4f46e5"
  }}
}}
"""
    return Response(content=manifest, media_type="application/json")
