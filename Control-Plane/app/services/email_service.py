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
    org_name: str | None = None
) -> None:
    """
    Sends an invitation email via Resend.
    If RESEND_API_KEY is not set, it merely logs the invite URL.
    """
    if not settings.RESEND_API_KEY:
        logger.warning("RESEND_API_KEY is not set. Email not sent. Invite URL: %s", invite_url)
        return

    resend.api_key = settings.RESEND_API_KEY

    # Formatting friendly expiration date (e.g., "Monday, September 4th")
    day = expires_at.day
    if 4 <= day <= 20 or 24 <= day <= 30:
        suffix = "th"
    else:
        suffix = ["st", "nd", "rd"][day % 10 - 1]
    
    friendly_expiry = expires_at.strftime(f"%A, %B {day}{suffix}")

    if org_name:
        subject = f"You have been invited to join {org_name}"
        body_text = f"You have been invited by <strong>{inviter_name}</strong> to join the <strong>{org_name}</strong> organization on Dart as an <strong>{role.capitalize()}</strong>! We would love for you to join us. By accepting this invitation, you will gain immediate access to our ecosystem, allowing you to seamlessly collaborate with your team, explore our suite of products, and streamline your workflow."
    else:
        subject = "You have been invited to join Dart!"
        body_text = f"You have been exclusively invited by <strong>{inviter_name}</strong> to set up your own organization on Dart! We would love to welcome you to our platform. By accepting this invitation, you will be able to establish your organization's workspace, unlock our premium products, and experience everything our ecosystem has to offer."

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

                <p style="font-size: 16px; margin-bottom: 12px; color: #4B5563;">Hi there,</p>
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

    try:
        r = resend.Emails.send({
            "from": settings.RESEND_FROM_EMAIL,
            "to": [to_email],
            "subject": subject,
            "html": html_content
        })
        logger.info("Successfully sent invite email to %s (id: %s)", to_email, r.get("id"))
    except Exception as e:
        logger.error("Failed to send invite email to %s: %s", to_email, e)
