import logging
import resend
from datetime import datetime

from app.core.config import settings

logger = logging.getLogger(__name__)

async def send_invite_email(
    to_email: str, 
    invite_url: str, 
    inviter_name: str, 
    role: str,
    expires_at: datetime,
    recipient_name: str,
    org_name: str | None = None
) -> bool:
    """
    Sends an invitation email via Resend.
    If RESEND_API_KEY is not set, it merely logs the invite URL.
    """
    if not settings.RESEND_API_KEY:
        logger.warning("RESEND_API_KEY is not set. Email not sent. Invite URL: %s", invite_url)
        return False

    resend.api_key = settings.RESEND_API_KEY

    # Formatting friendly expiration date (e.g., "Monday, September 4th")
    day = expires_at.day
    if 4 <= day <= 20 or 24 <= day <= 30:
        suffix = "th"
    else:
        suffix = ["st", "nd", "rd"][day % 10 - 1]
    
    friendly_expiry = expires_at.strftime(f"%A, %B {day}{suffix}")
    current_year = datetime.utcnow().year

    if org_name:
        # -------------------------------------------------------------
        # FLOW 1: Organization Owner Invite (Join existing org)
        # -------------------------------------------------------------
        subject = f"You have been invited to join {org_name}"
        body_text = f"You have been invited by <strong>{inviter_name}</strong> to join the <strong>{org_name}</strong> organization on Dart as an <strong>{role.capitalize()}</strong>! We would love for you to join us. By accepting this invitation, you will gain immediate access to our ecosystem, allowing you to seamlessly collaborate with your team, explore our suite of products, and streamline your workflow."
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>{subject}</title>
        </head>
        <body style="margin: 0; padding: 40px 20px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #F9FAFB; color: #333333;">
            <div style="max-width: 600px; margin: 0 auto;">
                <!-- Main Card -->
                <div style="background-color: #ffffff; border-radius: 12px; padding: 56px 48px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05); border: 1px solid #E5E7EB;">
                    
                    <div style="text-align: right; margin-bottom: 32px;">
                        <span style="font-size: 12px; font-weight: 600; color: #6B7280; background-color: #F3F4F6; padding: 6px 12px; border-radius: 999px;">
                            Valid until {friendly_expiry} ⏳
                        </span>
                    </div>

                    <h1 style="font-size: 36px; font-weight: 800; margin-top: 0; margin-bottom: 40px; letter-spacing: -1px; line-height: 1.2;">
                        You're invited to <span style="color: #007bff;">Dart</span>.
                    </h1>

                    <p style="font-size: 16px; margin-bottom: 12px; color: #4B5563;">Hi {recipient_name},</p>
                    <p style="font-size: 16px; font-weight: 600; margin-top: 0; margin-bottom: 32px;">
                        <a href="mailto:{to_email}" style="color: #111827; text-decoration: none;">{to_email}</a>
                    </p>

                    <p style="font-size: 16px; line-height: 1.7; margin-bottom: 28px; color: #4B5563;">
                        {body_text}
                    </p>
                    
                    <p style="font-size: 16px; line-height: 1.7; margin-bottom: 40px; color: #4B5563;">
                        Thank you for your interest in Dart. We are thrilled to have you!
                    </p>

                    <div style="text-align: center; margin-bottom: 40px;">
                        <a href="{invite_url}" style="display: inline-block; background-color: #007bff; color: #ffffff; text-decoration: none; font-size: 16px; font-weight: 600; padding: 16px 48px; border-radius: 8px;">Start</a>
                    </div>

                    <p style="font-size: 16px; line-height: 1.7; margin: 0; color: #4B5563;">
                        Looking forward to seeing you there,<br>
                        <strong style="color: #111827;">The Dart Team</strong>
                    </p>
                </div>

                <!-- Footer -->
                <div style="text-align: center; margin-top: 24px;">
                    <p style="font-size: 12px; color: #9CA3AF; margin: 0;">
                        This invitation was sent securely via Dart.<br>If you were not expecting this invitation, you can safely ignore this email.
                    </p>
                </div>
            </div>
        </body>
        </html>
        """
    else:
        # -------------------------------------------------------------
        # FLOW 2: Superadmin Invite (Create new org)
        # -------------------------------------------------------------
        subject = "You have been invited to INC Forensic"
        support_email = "support@braindart.tech"

        html_content = f"""<!DOCTYPE html>
<html lang="en" xmlns="http://www.w3.org/1999/xhtml" xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="x-apple-disable-message-reformatting">
<meta name="format-detection" content="telephone=no, date=no, address=no, email=no">
<title>You have been invited to INC Forensic</title>
<!--[if mso]>
<noscript><xml><o:OfficeDocumentSettings><o:PixelsPerInch>96</o:PixelsPerInch></o:OfficeDocumentSettings></xml></noscript>
<![endif]-->
<style>
  a {{ text-decoration: none; }}
  @media only screen and (max-width: 620px) {{
    .container {{ width: 100% !important; }}
    .pad {{ padding-left: 24px !important; padding-right: 24px !important; }}
    .h1 {{ font-size: 26px !important; line-height: 34px !important; }}
    .stack {{ display: block !important; width: 100% !important; padding-right: 0 !important; padding-bottom: 20px !important; }}
  }}
</style>
</head>
<body style="margin:0; padding:0; background-color:#f2efea; -webkit-font-smoothing:antialiased;">

<div style="display:none; font-size:1px; color:#f2efea; line-height:1px; max-height:0; max-width:0; opacity:0; overflow:hidden;">
  An invitation to establish your organisation on INC Forensic — medical evidence analytics for counsel and reviewing providers.&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;
</div>

<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#f2efea;">
<tr>
<td align="center" style="padding:32px 12px 48px 12px;">

  <table role="presentation" class="container" width="600" cellpadding="0" cellspacing="0" border="0" style="width:600px; max-width:600px;">

    <!-- Eyebrow -->
    <tr>
      <td align="center" style="padding:0 0 20px 0; font-family:Helvetica,Arial,sans-serif; font-size:11px; letter-spacing:1.4px; text-transform:uppercase; color:#8a827a;">
        Invitation &middot; Valid until {friendly_expiry}
      </td>
    </tr>

    <!-- Card -->
    <tr>
    <td style="background-color:#ffffff; border:1px solid #e4ded6; border-radius:2px;">

      <!-- Accent rule -->
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
        <tr><td style="height:3px; background-color:#7b2d26; font-size:0; line-height:0;">&nbsp;</td></tr>
      </table>

      <!-- Masthead -->
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
        <tr>
          <td class="pad" align="center" style="padding:40px 48px 34px 48px;">
            <div style="font-family:Georgia,'Times New Roman',serif; font-size:25px; letter-spacing:5px; color:#16181a; text-transform:uppercase;">
              INC&nbsp;Forensic
            </div>
            <div style="padding-top:9px; font-family:Helvetica,Arial,sans-serif; font-size:10px; letter-spacing:2.2px; text-transform:uppercase; color:#9a9188;">
              Medical Evidence Analytics
            </div>
          </td>
        </tr>
        <tr><td class="pad" style="padding:0 48px;"><div style="border-top:1px solid #ece6de; font-size:0; line-height:0;">&nbsp;</div></td></tr>
      </table>

      <!-- Body -->
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
        <tr>
          <td class="pad" style="padding:38px 48px 0 48px;">

            <h1 class="h1" style="margin:0 0 26px 0; font-family:Georgia,'Times New Roman',serif; font-size:30px; line-height:39px; font-weight:normal; color:#16181a;">
              You have been invited<br>to INC&nbsp;Forensic.
            </h1>

            <p style="margin:0 0 18px 0; font-family:Helvetica,Arial,sans-serif; font-size:15px; line-height:26px; color:#3c3833;">
              Dear {recipient_name},
            </p>

            <p style="margin:0 0 18px 0; font-family:Helvetica,Arial,sans-serif; font-size:15px; line-height:26px; color:#3c3833;">
              <strong style="color:#16181a;">Dr. Burns </strong> has invited you to establish an organisation account on INC&nbsp;Forensic, ahead of general availability.
            </p>

            <p style="margin:0 0 18px 0; font-family:Helvetica,Arial,sans-serif; font-size:15px; line-height:26px; color:#3c3833;">
              INC&nbsp;Forensic is a medico-legal analysis platform for attorneys, medical-legal consultants, reviewing providers, and claims professionals. You open a matter, load its records, and select the analysis you want. Every claim in every deliverable is cited to the page it came from, and nothing runs until you approve it.
            </p>

          </td>
        </tr>

        <!-- Two surfaces -->
        <tr>
          <td class="pad" style="padding:14px 48px 6px 48px;">
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#faf8f5; border:1px solid #ece6de;">
              <tr>
                <td style="padding:24px 26px 22px 26px;">
                  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
                    <tr>
                      <td class="stack" valign="top" width="50%" style="padding-right:16px; font-family:Helvetica,Arial,sans-serif;">
                        <div style="font-size:10px; letter-spacing:1.6px; text-transform:uppercase; color:#7b2d26; padding-bottom:7px;">The casework</div>
                        <div style="font-family:Georgia,'Times New Roman',serif; font-size:17px; color:#16181a; padding-bottom:7px;">MedRecs</div>
                        <div style="font-size:13px; line-height:22px; color:#5b554e;">Matters, record sets, and the five tiers of analysis &mdash; chronology, narrative assessment, adversarial audit, consulting strategy, and forensic diagnostics.</div>
                      </td>
                      <td class="stack" valign="top" width="50%" style="padding-left:16px; font-family:Helvetica,Arial,sans-serif;">
                        <div style="font-size:10px; letter-spacing:1.6px; text-transform:uppercase; color:#7b2d26; padding-bottom:7px;">The account</div>
                        <div style="font-family:Georgia,'Times New Roman',serif; font-size:17px; color:#16181a; padding-bottom:7px;">Control Plane</div>
                        <div style="font-size:13px; line-height:22px; color:#5b554e;">Your organisation &mdash; adding colleagues, reviewing matter statements, and settling billing. No case material is held here.</div>
                      </td>
                    </tr>
                  </table>
                </td>
              </tr>
            </table>
          </td>
        </tr>

        <tr>
          <td class="pad" style="padding:26px 48px 0 48px;">
            <p style="margin:0; font-family:Helvetica,Arial,sans-serif; font-size:15px; line-height:26px; color:#3c3833;">
              Accepting this invitation creates your organisation in Control Plane, from which you can invite the rest of your team. We verify every account before records can be loaded &mdash; you will hear from us within one business day.
            </p>
          </td>
        </tr>

        <!-- CTA -->
        <tr>
          <td class="pad" align="center" style="padding:34px 48px 10px 48px;">
            <!--[if mso]>
            <v:roundrect xmlns:v="urn:schemas-microsoft-com:vml" xmlns:w="urn:schemas-microsoft-com:office:word" href="{invite_url}" style="height:52px;v-text-anchor:middle;width:286px;" arcsize="4%" strokecolor="#16181a" fillcolor="#16181a">
              <w:anchorlock/>
              <center style="color:#ffffff;font-family:Helvetica,Arial,sans-serif;font-size:14px;letter-spacing:1px;">ACCEPT INVITATION</center>
            </v:roundrect>
            <![endif]-->
            <!--[if !mso]><!-- -->
            <a href="{invite_url}" style="display:inline-block; background-color:#16181a; color:#ffffff; font-family:Helvetica,Arial,sans-serif; font-size:13px; letter-spacing:1.6px; text-transform:uppercase; padding:17px 42px; border-radius:2px;">Accept invitation</a>
            <!--<![endif]-->
          </td>
        </tr>

        <tr>
          <td class="pad" align="center" style="padding:16px 48px 0 48px; font-family:Helvetica,Arial,sans-serif; font-size:12px; line-height:20px; color:#9a9188;">
            If the button does not open, copy this address into your browser:<br>
            <a href="{invite_url}" style="color:#7b2d26; word-break:break-all;">{invite_url}</a>
          </td>
        </tr>

        <tr>
          <td class="pad" style="padding:32px 48px 0 48px;"><div style="border-top:1px solid #ece6de; font-size:0; line-height:0;">&nbsp;</div></td>
        </tr>

        <!-- Pull quote -->
        <tr>
          <td class="pad" style="padding:28px 48px 0 48px;">
            <table role="presentation" cellpadding="0" cellspacing="0" border="0">
              <tr>
              </tr>
            </table>
          </td>
        </tr>

        <tr>
          <td class="pad" style="padding:30px 48px 44px 48px; font-family:Helvetica,Arial,sans-serif; font-size:15px; line-height:26px; color:#3c3833;">
            We look forward to working with you.<br>
            <span style="color:#8a827a;">&mdash; The INC&nbsp;Forensic Team</span>
          </td>
        </tr>
      </table>

    </td>
    </tr>

    <!-- Footer -->
    <tr>
      <td class="pad" style="padding:28px 30px 0 30px; font-family:Helvetica,Arial,sans-serif; font-size:11px; line-height:20px; color:#9a9188; text-align:center;">
        This invitation was sent to <a href="mailto:{to_email}" style="color:#8a827a;">{to_email}</a> and expires on {friendly_expiry}.<br>
        If you were not expecting it, you may disregard this message.
      </td>
    </tr>
    <tr>
      <td class="pad" style="padding:18px 30px 0 30px;"><div style="border-top:1px solid #e4ded6; font-size:0; line-height:0;">&nbsp;</div></td>
    </tr>
    <tr>
      <td class="pad" style="padding:18px 30px 0 30px; font-family:Helvetica,Arial,sans-serif; font-size:11px; line-height:19px; color:#a39a90; text-align:center;">
        Every claim cited to its page. Analysis, not opinion &mdash; the retained expert forms the opinions and signs the work.<br><br>
        For informational purposes only. Not legal or medical advice.<br>
        &copy; {current_year} INC&nbsp;Forensic &middot; <a href="mailto:{support_email}" style="color:#8a827a;">{support_email}</a>
      </td>
    </tr>

  </table>

</td>
</tr>
</table>

</body>
</html>
"""

    try:
        r = resend.Emails.send({
            "from": settings.RESEND_FROM_EMAIL,
            "to": [to_email],
            "subject": subject,
            "html": html_content
        })
        logger.info("Successfully sent invite email to %s (id: %s)", to_email, r.get("id"))
        return True
    except Exception as e:
        logger.error("Failed to send invite email to %s: %s", to_email, e)
        return False
