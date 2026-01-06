"""SheerID Military Verification
Based on ThanhNguyxn/SheerID-Verification-Tool
Session ID based verification with auto-retry until success
"""
import re
import random
import logging
import httpx
import uuid
import time
from typing import Dict, Optional, Tuple

from . import config
from .name_generator import (
    NameGenerator, 
    generate_email, 
    generate_birth_date, 
    generate_discharge_date,
    generate_fingerprint,
    generate_newrelic_headers,
    get_random_branch
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


# Error types that should trigger retry with different data
RETRY_ERRORS = [
    "outsideAgePerson",       # Age not in valid range
    "invalidPerson",          # Person not found in database
    "invalidBirthDate",       # Invalid birth date
    "notVerified",            # Could not verify
    "personalInfoError",      # Generic personal info error
    "organizationNotFound",   # Branch/org issue
]

# Errors that should NOT retry (permanent failures)
NO_RETRY_ERRORS = [
    "verificationLimitExceeded",  # Already verified
    "fraudSuspected",             # Fraud detected
    "tooManyAttempts",            # Rate limited
    "programClosed",              # Program not available
    "invalidLink",                # Bad link
]


class SheerIDVerifier:
    """SheerID Military Identity Verifier - Enhanced Version with Auto-Retry"""

    def __init__(self, verification_id: str):
        self.verification_id = verification_id
        self.fingerprint = generate_fingerprint()
        self.http_client = httpx.Client(timeout=30.0)
        self.attempt_count = 0
        self.used_combinations = set()  # Track used name/dob combos

    def __del__(self):
        if hasattr(self, "http_client"):
            self.http_client.close()

    @staticmethod
    def parse_verification_id(url: str) -> Optional[str]:
        """Parse verificationId from URL"""
        # First try to match verificationId parameter (priority)
        match = re.search(r"verificationId=([a-f0-9]+)", url, re.IGNORECASE)
        if match:
            return match.group(1)
        # Fallback: try to match verify/xxx (but not program ID)
        match = re.search(r"verify/([a-f0-9]{24,})(?:\?|$)", url, re.IGNORECASE)
        if match:
            return match.group(1)
        return None

    def _get_sheerid_headers(self) -> Dict:
        """Generate headers for SheerID API with NewRelic tracking"""
        nr = generate_newrelic_headers()
        
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "sec-ch-ua": '"Chromium";v="131", "Google Chrome";v="131"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "User-Agent": config.USER_AGENT,
            "Accept-Language": "en-US,en;q=0.9",
            "clientversion": "2.157.0",
            "clientname": "jslib",
            "newrelic": nr["newrelic"],
            "traceparent": nr["traceparent"],
            "tracestate": nr["tracestate"],
            "Origin": "https://services.sheerid.com",
        }

    def _sheerid_request(
        self, method: str, url: str, body: Optional[Dict] = None
    ) -> Tuple[Dict, int]:
        """Send SheerID API request with proper headers"""
        headers = self._get_sheerid_headers()

        try:
            response = self.http_client.request(
                method=method, url=url, json=body, headers=headers
            )
            try:
                data = response.json()
            except Exception:
                data = {"text": response.text}
            return data, response.status_code
        except Exception as e:
            logger.error(f"SheerID request failed: {e}")
            raise

    def _should_retry(self, error_ids: list) -> bool:
        """Check if we should retry with different data"""
        if not error_ids:
            return False
        
        # Check for no-retry errors first
        for err in error_ids:
            if err in NO_RETRY_ERRORS:
                return False
        
        # Check if any error is retryable
        for err in error_ids:
            if err in RETRY_ERRORS:
                return True
        
        return False

    def _get_fresh_data(self) -> Dict:
        """Get fresh veteran data for retry (different from previous attempts)"""
        from .veteran_data_scraper import get_veteran_for_verification
        
        max_attempts = 10
        for _ in range(max_attempts):
            veteran = get_veteran_for_verification()
            combo_key = f"{veteran['first_name']}|{veteran['last_name']}|{veteran['birth_date']}"
            
            if combo_key not in self.used_combinations:
                self.used_combinations.add(combo_key)
                return veteran
        
        # If all cached data exhausted, generate random
        logger.warning("⚠️ All cached data used, generating random data")
        name = NameGenerator.generate()
        return {
            "first_name": name["first_name"],
            "last_name": name["last_name"],
            "birth_date": generate_birth_date(),
            "branch": get_random_branch(),
            "discharge_date": generate_discharge_date(),
        }

    def _single_attempt(
        self,
        first_name: str,
        last_name: str,
        email: str,
        birth_date: str,
        discharge_date: str,
        branch: str,
        military_status: str = "VETERAN",
    ) -> Dict:
        """Execute single verification attempt"""
        self.attempt_count += 1
        
        # Get organization from branch
        org = config.BRANCH_ORG_MAP.get(branch, config.BRANCH_ORG_MAP["Army"])

        logger.info(f"🔄 Attempt #{self.attempt_count}")
        logger.info(f"🎖️ Military Info: {first_name} {last_name}")
        logger.info(f"🏛️ Branch: {org['name']}")
        logger.info(f"📅 Birth Date: {birth_date}")

        # Step 1: Collect Military Status
        logger.info("Step 1/2: Setting military status...")
        step1_body = {
            "status": military_status
        }

        step1_data, step1_status = self._sheerid_request(
            "POST",
            f"{config.SHEERID_API}/verification/{self.verification_id}/step/collectMilitaryStatus",
            step1_body,
        )

        if step1_status != 200:
            error_ids = step1_data.get("errorIds", [])
            
            # Check for rate limit
            if step1_status == 429 or "verificationLimitExceeded" in str(error_ids):
                return {
                    "success": False,
                    "retry": False,
                    "message": "Verification limit exceeded - data already verified",
                    "verification_id": self.verification_id,
                    "error_ids": error_ids,
                }
            
            return {
                "success": False,
                "retry": self._should_retry(error_ids),
                "message": f"Step 1 failed (status {step1_status}): {step1_data}",
                "error_ids": error_ids,
            }
        
        current_step = step1_data.get("currentStep", "")
        submission_url = step1_data.get("submissionUrl", "")
        
        logger.info(f"✅ Step 1 complete: {current_step}")

        # Step 2: Collect Inactive Military Personal Info
        logger.info("Step 2/2: Submitting personal information...")
        
        # Construct referer URL
        referer_url = f"{config.SHEERID_BASE_URL}/verify/{config.PROGRAM_ID}/?verificationId={self.verification_id}"
        
        # Use the submission URL from step 1, or construct it
        if not submission_url:
            submission_url = f"{config.SHEERID_API}/verification/{self.verification_id}/step/collectInactiveMilitaryPersonalInfo"

        # Generate fresh fingerprint for each attempt
        self.fingerprint = generate_fingerprint()

        step2_body = {
            "firstName": first_name,
            "lastName": last_name,
            "birthDate": birth_date,
            "email": email,
            "phoneNumber": "",
            "organization": {
                "id": org["id"],
                "name": org["name"]
            },
            "dischargeDate": discharge_date,
            "deviceFingerprintHash": self.fingerprint,
            "locale": "en-US",
            "country": "US",
            "metadata": {
                "marketConsentValue": False,
                "refererUrl": referer_url,
                "verificationId": self.verification_id,
                "flags": '{"doc-upload-considerations":"default","doc-upload-may24":"default","doc-upload-redesign-use-legacy-message-keys":false,"docUpload-assertion-checklist":"default","include-cvec-field-france-student":"not-labeled-optional","org-search-overlay":"default","org-selected-display":"default"}',
                "submissionOptIn": "By submitting the personal information above, I acknowledge that my personal information is being collected under the privacy policy of the business from which I am seeking a discount, and I understand that my personal information will be shared with SheerID as a processor/third-party service provider in order for SheerID to confirm my eligibility for a special offer."
            }
        }

        step2_data, step2_status = self._sheerid_request(
            "POST",
            submission_url,
            step2_body,
        )

        error_ids = step2_data.get("errorIds", [])

        # Check for rate limit / already verified
        if step2_status == 429 or "verificationLimitExceeded" in str(error_ids):
            return {
                "success": False,
                "retry": False,
                "message": "Verification limit exceeded - data already verified",
                "verification_id": self.verification_id,
                "error_ids": error_ids,
            }

        if step2_status != 200:
            return {
                "success": False,
                "retry": self._should_retry(error_ids),
                "message": f"Step 2 failed (status {step2_status}): {step2_data}",
                "error_ids": error_ids,
            }
        
        current_step = step2_data.get("currentStep", "")
        
        if current_step == "error":
            return {
                "success": False,
                "retry": self._should_retry(error_ids),
                "message": f"Verification error: {', '.join(error_ids) if error_ids else 'Unknown'}",
                "error_ids": error_ids,
            }

        logger.info(f"✅ Step 2 complete: {current_step}")
        
        redirect_url = step2_data.get("redirectUrl")

        # Check final status
        if current_step == "success":
            return {
                "success": True,
                "retry": False,
                "pending": False,
                "message": "🎉 Military verification successful!",
                "verification_id": self.verification_id,
                "redirect_url": redirect_url,
                "reward_code": step2_data.get("rewardCode"),
                "veteran_name": f"{first_name} {last_name}",
                "branch": org["name"],
                "status": step2_data,
            }
        
        # Document upload required - try again with different data
        if current_step == "docUpload":
            return {
                "success": False,
                "retry": True,  # Try again with different data
                "pending": True,
                "message": "📄 Document upload required - trying different data",
                "verification_id": self.verification_id,
                "status": step2_data,
            }
        
        # Email loop required
        if current_step == "emailLoop":
            return {
                "success": True,
                "retry": False,
                "pending": True,
                "message": "📧 Email verification required - check email inbox",
                "verification_id": self.verification_id,
                "email": email,
                "status": step2_data,
            }
        
        # Otherwise pending review
        return {
            "success": True,
            "retry": False,
            "pending": True,
            "message": "✨ Submitted, awaiting SheerID review",
            "verification_id": self.verification_id,
            "redirect_url": redirect_url,
            "veteran_name": f"{first_name} {last_name}",
            "branch": org["name"],
            "status": step2_data,
        }

    def verify_with_retry(
        self,
        max_retries: int = 10,
        delay_between_retries: float = 2.0,
        progress_callback=None,
    ) -> Dict:
        """
        Execute verification with auto-retry until success
        
        Args:
            max_retries: Maximum number of retry attempts
            delay_between_retries: Seconds to wait between retries
            progress_callback: Optional callback(attempt, max, message) for progress
        
        Returns:
            Dict with verification result
        """
        logger.info(f"🚀 Starting auto-retry verification (max {max_retries} attempts)")
        
        for attempt in range(1, max_retries + 1):
            # Get fresh veteran data for each attempt
            veteran = self._get_fresh_data()
            
            first_name = veteran["first_name"]
            last_name = veteran["last_name"]
            birth_date = veteran["birth_date"]
            branch = veteran.get("branch", get_random_branch())
            discharge_date = veteran.get("discharge_date", generate_discharge_date())
            email = generate_email()
            
            # Progress callback
            if progress_callback:
                progress_callback(
                    attempt, 
                    max_retries, 
                    f"🔄 Attempt {attempt}/{max_retries}: {first_name} {last_name} ({branch})"
                )
            
            logger.info(f"{'='*50}")
            logger.info(f"Attempt {attempt}/{max_retries}")
            logger.info(f"{'='*50}")
            
            result = self._single_attempt(
                first_name=first_name,
                last_name=last_name,
                email=email,
                birth_date=birth_date,
                discharge_date=discharge_date,
                branch=branch,
            )
            
            # Success! Return immediately
            if result.get("success"):
                logger.info(f"✅ SUCCESS on attempt {attempt}!")
                result["attempts"] = attempt
                return result
            
            # Check if we should retry
            if not result.get("retry", False):
                logger.info(f"❌ Cannot retry - {result.get('message')}")
                result["attempts"] = attempt
                return result
            
            # Log and continue
            error_ids = result.get("error_ids", [])
            logger.warning(f"⚠️ Attempt {attempt} failed: {error_ids}")
            
            if attempt < max_retries:
                logger.info(f"⏳ Waiting {delay_between_retries}s before retry...")
                time.sleep(delay_between_retries)
        
        # All retries exhausted
        return {
            "success": False,
            "retry": False,
            "message": f"❌ All {max_retries} attempts failed",
            "verification_id": self.verification_id,
            "attempts": max_retries,
        }

    def verify(
        self,
        first_name: str = None,
        last_name: str = None,
        email: str = None,
        birth_date: str = None,
        discharge_date: str = None,
        branch: str = None,
        military_status: str = "VETERAN",
        use_real_data: bool = True,
        auto_retry: bool = True,
        max_retries: int = 10,
    ) -> Dict:
        """
        Execute military verification flow
        
        Args:
            first_name: Veteran first name (optional, will auto-generate)
            last_name: Veteran last name (optional, will auto-generate)
            email: Email address (optional, will auto-generate)
            birth_date: Birth date YYYY-MM-DD (optional)
            discharge_date: Discharge date YYYY-MM-DD (optional)
            branch: Military branch name (optional)
            military_status: VETERAN, ACTIVE_DUTY, etc
            use_real_data: Use scraped real veteran data
            auto_retry: Enable auto-retry with different data
            max_retries: Max retry attempts if auto_retry enabled
        
        Returns:
            Dict with verification result
        """
        try:
            # If auto_retry enabled and no specific data provided, use retry mode
            if auto_retry and not first_name and not last_name:
                return self.verify_with_retry(max_retries=max_retries)
            
            # Single attempt mode
            if use_real_data and (not first_name or not last_name or not birth_date):
                from .veteran_data_scraper import get_veteran_for_verification
                veteran = get_veteran_for_verification()
                first_name = first_name or veteran["first_name"]
                last_name = last_name or veteran["last_name"]
                birth_date = birth_date or veteran["birth_date"]
                branch = branch or veteran["branch"]
                discharge_date = discharge_date or veteran["discharge_date"]
                logger.info("📋 Using real veteran data from database")
            else:
                if not first_name or not last_name:
                    name = NameGenerator.generate()
                    first_name = name["first_name"]
                    last_name = name["last_name"]

            if not branch:
                branch = get_random_branch()

            if not email:
                email = generate_email()
            if not birth_date:
                birth_date = generate_birth_date()
            if not discharge_date:
                discharge_date = generate_discharge_date()

            logger.info(f"📧 Email: {email}")
            logger.info(f"📅 Discharge Date: {discharge_date}")
            logger.info(f"⚔️ Military Status: {military_status}")
            logger.info(f"🔗 Verification ID: {self.verification_id}")

            result = self._single_attempt(
                first_name=first_name,
                last_name=last_name,
                email=email,
                birth_date=birth_date,
                discharge_date=discharge_date,
                branch=branch,
                military_status=military_status,
            )
            
            result["attempts"] = 1
            return result

        except Exception as e:
            logger.error(f"❌ Verification failed: {e}")
            return {
                "success": False, 
                "message": str(e), 
                "verification_id": self.verification_id,
                "attempts": self.attempt_count,
            }


def main():
    """Main function - CLI interface"""
    import sys

    print("=" * 60)
    print("SheerID Military Verification Tool")
    print("Based on ThanhNguyxn/SheerID-Verification-Tool")
    print("Auto-retry until success enabled!")
    print("=" * 60)
    print()

    if len(sys.argv) > 1:
        url = sys.argv[1]
    else:
        url = input("Enter SheerID verification URL: ").strip()

    if not url:
        print("❌ Error: No URL provided")
        sys.exit(1)

    verification_id = SheerIDVerifier.parse_verification_id(url)
    if not verification_id:
        print("❌ Error: Invalid verification ID format")
        sys.exit(1)

    print(f"✅ Parsed verification ID: {verification_id}")
    print()

    verifier = SheerIDVerifier(verification_id)
    result = verifier.verify(auto_retry=True, max_retries=10)

    print()
    print("=" * 60)
    print("Verification Result:")
    print("=" * 60)
    print(f"Status: {'✅ Success' if result['success'] else '❌ Failed'}")
    print(f"Attempts: {result.get('attempts', 1)}")
    print(f"Message: {result['message']}")
    if result.get("veteran_name"):
        print(f"Veteran: {result['veteran_name']}")
    if result.get("branch"):
        print(f"Branch: {result['branch']}")
    if result.get("redirect_url"):
        print(f"Redirect URL: {result['redirect_url']}")
    if result.get("reward_code"):
        print(f"Reward Code: {result['reward_code']}")
    print("=" * 60)

    return 0 if result["success"] else 1


if __name__ == "__main__":
    exit(main())
