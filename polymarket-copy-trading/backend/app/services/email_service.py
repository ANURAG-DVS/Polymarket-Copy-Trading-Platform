import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

async def send_email(to_email: str, subject: str, html_content: str):
    """Send email using SMTP"""
    try:
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = settings.EMAIL_FROM
        message["To"] = to_email
        
        html_part = MIMEText(html_content, "html")
        message.attach(html_part)
        
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            if settings.SMTP_USER and settings.SMTP_PASSWORD:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(message)
        
        logger.info(f"Email sent to: {to_email}")
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {str(e)}")

async def send_password_reset_email(email: str, reset_token: str):
    """Send password reset email"""
    reset_url = f"{settings.FRONTEND_URL}/reset-password?token={reset_token}"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .button {{ 
                display: inline-block; 
                padding: 12px 24px; 
                background-color: #4F46E5; 
                color: white; 
                text-decoration: none; 
                border-radius: 6px;
                margin: 20px 0;
            }}
            .footer {{ margin-top: 30px; font-size: 12px; color: #666; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2>Reset Your Password</h2>
            <p>You recently requested to reset your password for your Polymarket Copy Trading account.</p>
            <p>Click the button below to reset your password:</p>
            <a href="{reset_url}" class="button">Reset Password</a>
            <p>Or copy and paste this link into your browser:</p>
            <p><a href="{reset_url}">{reset_url}</a></p>
            <p>This link will expire in 1 hour.</p>
            <p>If you didn't request a password reset, please ignore this email.</p>
            <div class="footer">
                <p>© 2024 Polymarket Copy Trading. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    await send_email(email, "Reset Your Password", html_content)

async def send_welcome_email(email: str, username: str):
    """Send welcome email to new user"""
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            h2 {{ color: #4F46E5; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2>Welcome to Polymarket Copy Trading!</h2>
            <p>Hi {username},</p>
            <p>Thank you for registering with Polymarket Copy Trading. Your account has been successfully created.</p>
            <p>You can now:</p>
            <ul>
                <li>Browse top traders on the platform</li>
                <li>Set up copy trading relationships</li>
                <li>Monitor your portfolio performance</li>
                <li>Configure your trading preferences</li>
            </ul>
            <p>Get started by exploring our <a href="{settings.FRONTEND_URL}/traders">Trader Leaderboard</a>.</p>
            <p>Happy trading!</p>
            <p>Best regards,<br>The Polymarket Copy Trading Team</p>
        </div>
    </body>
    </html>
    """
    
    await send_email(email, "Welcome to Polymarket Copy Trading!", html_content)
