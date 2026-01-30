"""
Email service using Resend for transactional emails.

Used for:
- Sending lead notifications to vendors when their quote is displayed
"""

import os
import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# Try to import resend, but don't fail if not installed
try:
    import resend
    RESEND_AVAILABLE = True
except ImportError:
    RESEND_AVAILABLE = False
    logger.warning("Resend not installed. Email functionality will be disabled.")


class EmailService:
    """Service for sending transactional emails via Resend."""
    
    def __init__(self):
        self.api_key = os.environ.get("RESEND_API_KEY")
        self.from_email = os.environ.get("RESEND_FROM_EMAIL", "leads@iivy.io")
        self.enabled = RESEND_AVAILABLE and bool(self.api_key)
        
        if self.enabled:
            resend.api_key = self.api_key
        else:
            logger.warning("Email service disabled: RESEND_API_KEY not set or resend not installed")
    
    async def send_vendor_lead_notification(
        self,
        vendor_email: str,
        vendor_company_name: str,
        customer_name: str,
        customer_email: str,
        segment_name: str,
        project_sqft: int,
        project_location: str,
        project_name: str,
        quoted_rate: float,
        quoted_total: float,
        additional_requirements: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send a lead notification email to a vendor when their quote is displayed.
        
        Args:
            vendor_email: The vendor's email address
            vendor_company_name: The vendor's company name
            customer_name: The customer's name
            customer_email: The customer's email address
            segment_name: The service segment (e.g., "Roofing")
            project_sqft: The project size in square feet
            project_location: The project location (city, region, country)
            project_name: The name of the project
            quoted_rate: The rate per sqft quoted
            quoted_total: The total amount quoted
            additional_requirements: Any additional requirements from the customer
            
        Returns:
            Dict with email status and message ID if sent
        """
        if not self.enabled:
            logger.warning(f"Email not sent (disabled): Lead notification to {vendor_email}")
            return {
                "status": "disabled",
                "message": "Email service is disabled"
            }
        
        try:
            # Build the email HTML
            html_content = self._build_lead_notification_html(
                vendor_company_name=vendor_company_name,
                customer_name=customer_name,
                customer_email=customer_email,
                segment_name=segment_name,
                project_sqft=project_sqft,
                project_location=project_location,
                project_name=project_name,
                quoted_rate=quoted_rate,
                quoted_total=quoted_total,
                additional_requirements=additional_requirements
            )
            
            # Build plain text version
            text_content = self._build_lead_notification_text(
                vendor_company_name=vendor_company_name,
                customer_name=customer_name,
                customer_email=customer_email,
                segment_name=segment_name,
                project_sqft=project_sqft,
                project_location=project_location,
                project_name=project_name,
                quoted_rate=quoted_rate,
                quoted_total=quoted_total,
                additional_requirements=additional_requirements
            )
            
            # Extract city from location for subject
            city = project_location.split(",")[0].strip() if project_location else "your area"
            
            params = {
                "from": f"IIVY Leads <{self.from_email}>",
                "to": [vendor_email],
                "subject": f"🎯 New Lead: {segment_name} in {city}",
                "html": html_content,
                "text": text_content,
            }
            
            email_response = resend.Emails.send(params)
            
            logger.info(f"Lead notification sent to {vendor_email}: {email_response.get('id')}")
            
            return {
                "status": "sent",
                "message_id": email_response.get("id"),
                "sent_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to send lead notification to {vendor_email}: {str(e)}")
            return {
                "status": "failed",
                "error": str(e)
            }
    
    def _build_lead_notification_html(
        self,
        vendor_company_name: str,
        customer_name: str,
        customer_email: str,
        segment_name: str,
        project_sqft: int,
        project_location: str,
        project_name: str,
        quoted_rate: float,
        quoted_total: float,
        additional_requirements: Optional[str] = None
    ) -> str:
        """Build HTML email content for lead notification."""
        
        requirements_section = ""
        if additional_requirements:
            requirements_section = f"""
            <tr>
                <td style="padding: 8px 0; color: #6b7280;">Requirements:</td>
                <td style="padding: 8px 0; color: #ffffff; font-weight: 500;">{additional_requirements}</td>
            </tr>
            """
        
        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; background-color: #0a0a0a; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: #0a0a0a;">
        <tr>
            <td align="center" style="padding: 40px 20px;">
                <table role="presentation" width="600" cellspacing="0" cellpadding="0" style="background-color: #111827; border-radius: 16px; overflow: hidden;">
                    
                    <!-- Header -->
                    <tr>
                        <td style="background: linear-gradient(135deg, #10b981 0%, #059669 100%); padding: 32px; text-align: center;">
                            <h1 style="margin: 0; color: #ffffff; font-size: 24px; font-weight: 700;">
                                🎯 New Lead for {vendor_company_name}
                            </h1>
                            <p style="margin: 8px 0 0 0; color: rgba(255,255,255,0.9); font-size: 16px;">
                                Your quote was just viewed by a potential customer!
                            </p>
                        </td>
                    </tr>
                    
                    <!-- Project Details -->
                    <tr>
                        <td style="padding: 32px;">
                            <h2 style="margin: 0 0 16px 0; color: #10b981; font-size: 14px; text-transform: uppercase; letter-spacing: 1px;">
                                📋 Project Details
                            </h2>
                            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="border: 1px solid #374151; border-radius: 8px; overflow: hidden;">
                                <tr>
                                    <td style="padding: 16px; background-color: #1f2937;">
                                        <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
                                            <tr>
                                                <td style="padding: 8px 0; color: #6b7280;">Service:</td>
                                                <td style="padding: 8px 0; color: #ffffff; font-weight: 500;">{segment_name}</td>
                                            </tr>
                                            <tr>
                                                <td style="padding: 8px 0; color: #6b7280;">Project Size:</td>
                                                <td style="padding: 8px 0; color: #ffffff; font-weight: 500;">{project_sqft:,} sqft</td>
                                            </tr>
                                            <tr>
                                                <td style="padding: 8px 0; color: #6b7280;">Location:</td>
                                                <td style="padding: 8px 0; color: #ffffff; font-weight: 500;">{project_location}</td>
                                            </tr>
                                            <tr>
                                                <td style="padding: 8px 0; color: #6b7280;">Project Name:</td>
                                                <td style="padding: 8px 0; color: #ffffff; font-weight: 500;">{project_name}</td>
                                            </tr>
                                            {requirements_section}
                                        </table>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                    
                    <!-- Your Quote -->
                    <tr>
                        <td style="padding: 0 32px 32px 32px;">
                            <h2 style="margin: 0 0 16px 0; color: #10b981; font-size: 14px; text-transform: uppercase; letter-spacing: 1px;">
                                💰 Your Quote
                            </h2>
                            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="border: 1px solid #374151; border-radius: 8px; overflow: hidden;">
                                <tr>
                                    <td style="padding: 16px; background-color: #1f2937;">
                                        <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
                                            <tr>
                                                <td style="padding: 8px 0; color: #6b7280;">Rate:</td>
                                                <td style="padding: 8px 0; color: #10b981; font-weight: 600; font-size: 18px;">${quoted_rate:.2f}/sqft</td>
                                            </tr>
                                            <tr>
                                                <td style="padding: 8px 0; color: #6b7280;">Total Estimate:</td>
                                                <td style="padding: 8px 0; color: #10b981; font-weight: 600; font-size: 18px;">${quoted_total:,.2f}</td>
                                            </tr>
                                        </table>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                    
                    <!-- Customer Contact -->
                    <tr>
                        <td style="padding: 0 32px 32px 32px;">
                            <h2 style="margin: 0 0 16px 0; color: #10b981; font-size: 14px; text-transform: uppercase; letter-spacing: 1px;">
                                👤 Customer Contact
                            </h2>
                            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="border: 1px solid #374151; border-radius: 8px; overflow: hidden; background-color: #1f2937;">
                                <tr>
                                    <td style="padding: 20px;">
                                        <p style="margin: 0 0 4px 0; color: #ffffff; font-size: 18px; font-weight: 600;">
                                            {customer_name or "Project Owner"}
                                        </p>
                                        <p style="margin: 0; color: #10b981; font-size: 16px;">
                                            <a href="mailto:{customer_email}" style="color: #10b981; text-decoration: none;">
                                                {customer_email}
                                            </a>
                                        </p>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                    
                    <!-- CTA Button -->
                    <tr>
                        <td style="padding: 0 32px 32px 32px;">
                            <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
                                <tr>
                                    <td align="center">
                                        <a href="mailto:{customer_email}?subject=Re: {segment_name} Quote for {project_name}&body=Hi {customer_name or 'there'},%0A%0AI saw your request for {segment_name} services and would love to discuss your project.%0A%0ABest regards,%0A{vendor_company_name}" 
                                           style="display: inline-block; background: linear-gradient(135deg, #10b981 0%, #059669 100%); color: #ffffff; padding: 16px 32px; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 16px;">
                                            📧 Contact Customer Now
                                        </a>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                    
                    <!-- Footer -->
                    <tr>
                        <td style="padding: 24px 32px; background-color: #0d1117; border-top: 1px solid #374151;">
                            <p style="margin: 0 0 8px 0; color: #6b7280; font-size: 12px; text-align: center;">
                                You were charged $250 for this lead.
                            </p>
                            <p style="margin: 0; color: #6b7280; font-size: 12px; text-align: center;">
                                This customer is actively looking for quotes. Reach out quickly to win this project!
                            </p>
                        </td>
                    </tr>
                    
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
        """
    
    def _build_lead_notification_text(
        self,
        vendor_company_name: str,
        customer_name: str,
        customer_email: str,
        segment_name: str,
        project_sqft: int,
        project_location: str,
        project_name: str,
        quoted_rate: float,
        quoted_total: float,
        additional_requirements: Optional[str] = None
    ) -> str:
        """Build plain text email content for lead notification."""
        
        requirements_line = f"\nRequirements: {additional_requirements}" if additional_requirements else ""
        
        return f"""
🎯 New Lead for {vendor_company_name}

Your quote was just viewed by a potential customer!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📋 PROJECT DETAILS

Service: {segment_name}
Project Size: {project_sqft:,} sqft
Location: {project_location}
Project Name: {project_name}{requirements_line}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💰 YOUR QUOTE

Rate: ${quoted_rate:.2f}/sqft
Total Estimate: ${quoted_total:,.2f}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

👤 CUSTOMER CONTACT

{customer_name or "Project Owner"}
{customer_email}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🚀 ACT NOW

This customer is actively looking for quotes.
Reach out quickly to win this project!

Reply to this email or contact the customer directly at:
{customer_email}

---
You were charged $250 for this lead.
        """


# Singleton instance
_email_service = None

def get_email_service() -> EmailService:
    """Get the singleton email service instance."""
    global _email_service
    if _email_service is None:
        _email_service = EmailService()
    return _email_service
