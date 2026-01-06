"""ChatGPT Military SheerID Verification Module
Based on ThanhNguyxn/SheerID-Verification-Tool
"""

from .sheerid_verifier import SheerIDVerifier
from .name_generator import (
    NameGenerator, 
    generate_email, 
    generate_birth_date, 
    generate_discharge_date,
    generate_fingerprint,
    generate_newrelic_headers,
    get_random_branch
)
from .veteran_data_scraper import (
    get_real_veteran_data,
    get_veteran_for_verification,
    VeteranDataScraper
)
from . import config

__all__ = [
    'SheerIDVerifier', 
    'NameGenerator', 
    'generate_email', 
    'generate_birth_date', 
    'generate_discharge_date',
    'generate_fingerprint',
    'generate_newrelic_headers',
    'get_random_branch',
    'get_real_veteran_data',
    'get_veteran_for_verification',
    'VeteranDataScraper',
    'config'
]

