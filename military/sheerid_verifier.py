"""SheerID Military Verification"""
import re
import random
import logging
import httpx
from typing import Dict, Optional, Tuple

from . import config
from .name_generator import NameGenerator, generate_email, generate_birth_date, generate_discharge_date

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


class SheerIDVerifier:
    """SheerID Military Identity Verifier"""

    def __init__(self, verification_id: str):
        self.verification_id = verification_id
        self.http_client = httpx.Client(timeout=30.0)

    def __del__(self):
        if hasattr(self, "http_client"):
            self.http_client.close()

    @staticmethod
    def parse_verification_id(url: str) -> Optional[str]:
        """Parse verificationId from URL"""
        match = re.search(r"verificationId=([a-f0-9]+)", url, re.IGNORECASE)
        if match:
            return match.group(1)
        return None

    def _sheerid_request(
        self, method: str, url: str, body: Optional[Dict] = None
    ) -> Tuple[Dict, int]:
        """Send SheerID API request"""
        headers = {
            "Content-Type": "application/json",
        }

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

    def verify(
        self,
        first_name: str = None,
        last_name: str = None,
        email: str = None,
        birth_date: str = None,
        discharge_date: str = None,
        org_id: str = None,
        military_status: str = "VETERAN",
    ) -> Dict:
        """Execute military verification flow"""
        try:
            # Generate random info if not provided
            if not first_name or not last_name:
                name = NameGenerator.generate()
                first_name = name["first_name"]
                last_name = name["last_name"]

            org_id = org_id or config.DEFAULT_ORG_ID
            org = config.ORGANIZATIONS[org_id]

            if not email:
                email = generate_email()
            if not birth_date:
                birth_date = generate_birth_date()
            if not discharge_date:
                discharge_date = generate_discharge_date()

            logger.info(f"Military Info: {first_name} {last_name}")
            logger.info(f"Email: {email}")
            logger.info(f"Organization: {org['name']}")
            logger.info(f"Birth Date: {birth_date}")
            logger.info(f"Discharge Date: {discharge_date}")
            logger.info(f"Military Status: {military_status}")
            logger.info(f"Verification ID: {self.verification_id}")

            # Step 1: Collect Military Status
            logger.info("Step 1/2: Setting military status...")
            step1_body = {
                "status": military_status
            }

            step1_data, step1_status = self._sheerid_request(
                "POST",
                f"{config.SHEERID_BASE_URL}/rest/v2/verification/{self.verification_id}/step/collectMilitaryStatus",
                step1_body,
            )

            if step1_status != 200:
                raise Exception(f"Step 1 failed (status {step1_status}): {step1_data}")
            
            current_step = step1_data.get("currentStep", "")
            submission_url = step1_data.get("submissionUrl", "")
            
            logger.info(f"✅ Step 1 complete: {current_step}")
            logger.info(f"Submission URL: {submission_url}")

            # Step 2: Collect Inactive Military Personal Info
            logger.info("Step 2/2: Submitting personal information...")
            
            # Use the submission URL from step 1, or construct it
            if not submission_url:
                submission_url = f"{config.SHEERID_BASE_URL}/rest/v2/verification/{self.verification_id}/step/collectInactiveMilitaryPersonalInfo"

            step2_body = {
                "firstName": first_name,
                "lastName": last_name,
                "birthDate": birth_date,
                "email": email,
                "phoneNumber": "",
                "organization": {
                    "id": int(org_id),
                    "name": org["name"]
                },
                "dischargeDate": discharge_date,
                "locale": "en-US",
                "country": "US",
                "metadata": {
                    "marketConsentValue": False,
                    "refererUrl": "",
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

            if step2_status != 200:
                raise Exception(f"Step 2 failed (status {step2_status}): {step2_data}")
            
            if step2_data.get("currentStep") == "error":
                error_msg = ", ".join(step2_data.get("errorIds", ["Unknown error"]))
                raise Exception(f"Step 2 error: {error_msg}")

            logger.info(f"✅ Step 2 complete: {step2_data.get('currentStep')}")
            
            final_status = step2_data
            redirect_url = final_status.get("redirectUrl")

            # Check if verification succeeded immediately
            if final_status.get("currentStep") == "success":
                return {
                    "success": True,
                    "pending": False,
                    "message": "Military verification successful!",
                    "verification_id": self.verification_id,
                    "redirect_url": redirect_url,
                    "reward_code": final_status.get("rewardCode"),
                    "status": final_status,
                }
            
            # Otherwise pending
            return {
                "success": True,
                "pending": True,
                "message": "Submitted, awaiting review",
                "verification_id": self.verification_id,
                "redirect_url": redirect_url,
                "status": final_status,
            }

        except Exception as e:
            logger.error(f"❌ Verification failed: {e}")
            return {"success": False, "message": str(e), "verification_id": self.verification_id}


def main():
    """Main function - CLI interface"""
    import sys

    print("=" * 60)
    print("SheerID Military Verification Tool")
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
    result = verifier.verify()

    print()
    print("=" * 60)
    print("Verification Result:")
    print("=" * 60)
    print(f"Status: {'✅ Success' if result['success'] else '❌ Failed'}")
    print(f"Message: {result['message']}")
    if result.get("redirect_url"):
        print(f"Redirect URL: {result['redirect_url']}")
    if result.get("reward_code"):
        print(f"Reward Code: {result['reward_code']}")
    print("=" * 60)

    return 0 if result["success"] else 1


if __name__ == "__main__":
    exit(main())
