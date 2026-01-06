"""
Veteran Data Scraper
Scrapes real veteran data from official public sources for SheerID verification
Auto-scrapes from VA Grave Locator, CMOHS, and other public memorial sites

Enhanced with:
- Multi-source data aggregation
- Demographically accurate data generation
- Data quality validation
- Realistic military career patterns
"""
import random
import httpx
import re
import logging
import json
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# ============== DEMOGRAPHIC CONSTANTS (Based on 2023 DMDC Reports) ==============

# Branch distribution (real military demographics)
BRANCH_DISTRIBUTION = {
    "Army": 0.36,
    "Navy": 0.24,
    "Air Force": 0.22,
    "Marine Corps": 0.13,
    "Coast Guard": 0.05
}

# Age distribution for veterans seeking verification
AGE_DISTRIBUTION = {
    (21, 30): 0.25,   # Post-9/11 recent veterans
    (31, 40): 0.30,   # Iraq/Afghanistan era
    (41, 50): 0.25,   # Gulf War era
    (51, 60): 0.15,   # Late Cold War
    (61, 70): 0.05,   # Vietnam era (older)
}

# Common MOS/Rating by branch
MOS_BY_BRANCH = {
    "Army": ["11B", "92Y", "68W", "12B", "88M", "25B", "91B", "31B", "35F", "13B"],
    "Navy": ["HM", "BM", "MM", "IT", "LS", "GM", "EM", "YN", "MA", "OS"],
    "Air Force": ["3P0X1", "2T2X1", "1C1X1", "3E0X1", "4Y0X1", "1N0X1", "2A3X3"],
    "Marine Corps": ["0311", "0331", "0341", "0811", "1833", "0651", "3531", "0621"],
    "Coast Guard": ["BM", "MK", "EM", "HS", "OS", "ME", "DC", "ET"]
}

# Veteran era templates
VETERAN_TEMPLATES = [
    {
        "era": "Post-9/11",
        "age_range": (25, 45),
        "common_branches": ["Army", "Marine Corps", "Navy", "Air Force"],
        "service_years": (2001, 2024),
        "weight": 0.50  # Most common for verification
    },
    {
        "era": "Gulf War",
        "age_range": (45, 60),
        "common_branches": ["Army", "Air Force", "Navy"],
        "service_years": (1990, 2000),
        "weight": 0.30
    },
    {
        "era": "Cold War",
        "age_range": (55, 70),
        "common_branches": ["Army", "Navy", "Air Force"],
        "service_years": (1975, 1990),
        "weight": 0.15
    },
    {
        "era": "Vietnam",
        "age_range": (70, 80),
        "common_branches": ["Army", "Marine Corps"],
        "service_years": (1964, 1975),
        "weight": 0.05
    }
]

# Common American first names (top military names from VA data)
FIRST_NAMES_MALE = [
    "JAMES", "JOHN", "ROBERT", "MICHAEL", "WILLIAM", "DAVID", "RICHARD", "JOSEPH",
    "THOMAS", "CHARLES", "CHRISTOPHER", "DANIEL", "MATTHEW", "ANTHONY", "MARK",
    "DONALD", "STEVEN", "PAUL", "ANDREW", "JOSHUA", "KENNETH", "KEVIN", "BRIAN",
    "GEORGE", "TIMOTHY", "RONALD", "EDWARD", "JASON", "JEFFREY", "RYAN",
    "JACOB", "NICHOLAS", "GARY", "ERIC", "JONATHAN", "STEPHEN", "LARRY", "JUSTIN",
    "SCOTT", "BRANDON", "BENJAMIN", "SAMUEL", "RAYMOND", "GREGORY", "FRANK",
    "ALEXANDER", "PATRICK", "JACK", "DENNIS", "JERRY", "TYLER", "AARON", "JOSE",
    "ADAM", "HENRY", "NATHAN", "DOUGLAS", "ZACHARY", "PETER", "KYLE"
]

# Common American last names (top from Census)
LAST_NAMES = [
    "SMITH", "JOHNSON", "WILLIAMS", "BROWN", "JONES", "GARCIA", "MILLER", "DAVIS",
    "RODRIGUEZ", "MARTINEZ", "HERNANDEZ", "LOPEZ", "GONZALEZ", "WILSON", "ANDERSON",
    "THOMAS", "TAYLOR", "MOORE", "JACKSON", "MARTIN", "LEE", "PEREZ", "THOMPSON",
    "WHITE", "HARRIS", "SANCHEZ", "CLARK", "RAMIREZ", "LEWIS", "ROBINSON",
    "WALKER", "YOUNG", "ALLEN", "KING", "WRIGHT", "SCOTT", "TORRES", "NGUYEN",
    "HILL", "FLORES", "GREEN", "ADAMS", "NELSON", "BAKER", "HALL", "RIVERA",
    "CAMPBELL", "MITCHELL", "CARTER", "ROBERTS", "GOMEZ", "PHILLIPS", "EVANS",
    "TURNER", "DIAZ", "PARKER", "CRUZ", "EDWARDS", "COLLINS", "REYES"
]

# Search last names for scraping
SEARCH_LAST_NAMES = [name.title() for name in LAST_NAMES[:40]]

# Branch mapping
BRANCH_MAP = {
    "ARMY": "Army",
    "USA": "Army",
    "US ARMY": "Army",
    "NAVY": "Navy",
    "USN": "Navy",
    "US NAVY": "Navy",
    "AIR FORCE": "Air Force",
    "USAF": "Air Force",
    "US AIR FORCE": "Air Force",
    "MARINE CORPS": "Marine Corps",
    "MARINES": "Marine Corps",
    "USMC": "Marine Corps",
    "US MARINE CORPS": "Marine Corps",
    "COAST GUARD": "Coast Guard",
    "USCG": "Coast Guard",
    "US COAST GUARD": "Coast Guard",
    "SPACE FORCE": "Space Force",
    "USSF": "Space Force",
}


class VeteranDataScraper:
    """Auto-scraper for veteran data from public memorial sources"""
    
    def __init__(self):
        self.client = httpx.Client(
            timeout=30.0, 
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
                "Accept": "application/json, text/html, */*",
                "Accept-Language": "en-US,en;q=0.9",
            }
        )
        self.scraped_cache = []  # Cache scraped results
        self.used_data = set()  # Track used combinations
    
    def __del__(self):
        if hasattr(self, "client"):
            self.client.close()
    
    def _normalize_branch(self, branch_str: str) -> str:
        """Normalize branch name to standard format"""
        if not branch_str:
            return "Army"
        branch_upper = branch_str.upper().strip()
        for key, value in BRANCH_MAP.items():
            if key in branch_upper:
                return value
        return "Army"
    
    def _parse_date(self, date_str: str) -> Optional[str]:
        """Parse various date formats to YYYY-MM-DD"""
        if not date_str:
            return None
        
        # Try various formats
        formats = [
            "%Y-%m-%d",
            "%m/%d/%Y",
            "%m-%d-%Y",
            "%B %d, %Y",
            "%b %d, %Y",
            "%d %B %Y",
            "%d %b %Y",
        ]
        
        for fmt in formats:
            try:
                dt = datetime.strptime(date_str.strip(), fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue
        
        return None

    def scrape_va_grave_locator(self, last_name: str = None, max_results: int = 20) -> List[Dict]:
        """
        Scrape VA National Grave Locator
        https://gravelocator.cem.va.gov/ngl/
        """
        if not last_name:
            last_name = random.choice(SEARCH_LAST_NAMES)
        
        veterans = []
        
        try:
            logger.info(f"🔍 Scraping VA Grave Locator for: {last_name}")
            
            # Search API
            url = "https://gravelocator.cem.va.gov/ngl/api/search"
            
            payload = {
                "lastName": last_name,
                "cemeteryType": "N",  # National cemetery
                "pageSize": max_results,
                "pageNumber": 1
            }
            
            response = self.client.post(url, json=payload)
            
            if response.status_code == 200:
                data = response.json()
                records = data.get("data", []) or data.get("records", []) or []
                
                for record in records[:max_results]:
                    first_name = record.get("firstName", "").strip().upper()
                    last_name = record.get("lastName", "").strip().upper()
                    branch = self._normalize_branch(record.get("branchOfService", ""))
                    birth_date = self._parse_date(record.get("dateOfBirth", ""))
                    
                    if first_name and last_name and birth_date:
                        veterans.append({
                            "first_name": first_name,
                            "last_name": last_name,
                            "branch": branch,
                            "birth_date": birth_date,
                            "source": "VA_GRAVE_LOCATOR"
                        })
                
                logger.info(f"✅ Found {len(veterans)} veterans from VA Grave Locator")
            
        except Exception as e:
            logger.error(f"VA Grave Locator error: {e}")
        
        return veterans

    def scrape_arlington_cemetery(self, last_name: str = None, max_results: int = 20) -> List[Dict]:
        """
        Scrape Arlington National Cemetery Explorer
        https://ancexplorer.army.mil/publicwmv/
        """
        if not last_name:
            last_name = random.choice(SEARCH_LAST_NAMES)
        
        veterans = []
        
        try:
            logger.info(f"🔍 Scraping Arlington Cemetery for: {last_name}")
            
            # Arlington API search
            url = "https://ancexplorer.army.mil/publicwmv/api/search"
            
            payload = {
                "searchText": last_name,
                "pageSize": max_results,
                "pageIndex": 0
            }
            
            headers = {
                "Content-Type": "application/json",
                "Origin": "https://ancexplorer.army.mil",
                "Referer": "https://ancexplorer.army.mil/publicwmv/"
            }
            
            response = self.client.post(url, json=payload, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                records = data.get("results", []) or data.get("data", []) or []
                
                for record in records[:max_results]:
                    first_name = record.get("firstName", "").strip().upper()
                    last_name = record.get("lastName", "").strip().upper()
                    branch = self._normalize_branch(record.get("branch", "") or record.get("service", ""))
                    birth_date = self._parse_date(record.get("birthDate", "") or record.get("dateOfBirth", ""))
                    
                    if first_name and last_name and birth_date:
                        veterans.append({
                            "first_name": first_name,
                            "last_name": last_name,
                            "branch": branch,
                            "birth_date": birth_date,
                            "source": "ARLINGTON_CEMETERY"
                        })
                
                logger.info(f"✅ Found {len(veterans)} veterans from Arlington Cemetery")
            
        except Exception as e:
            logger.error(f"Arlington Cemetery error: {e}")
        
        return veterans

    def scrape_vlm(self, last_name: str = None, max_results: int = 20) -> List[Dict]:
        """
        Scrape Veterans Legacy Memorial
        https://www.vlm.cem.va.gov/
        """
        if not last_name:
            last_name = random.choice(SEARCH_LAST_NAMES)
        
        veterans = []
        
        try:
            logger.info(f"🔍 Scraping Veterans Legacy Memorial for: {last_name}")
            
            url = f"https://www.vlm.cem.va.gov/api/veteran/search"
            
            params = {
                "lastName": last_name,
                "pageSize": max_results,
                "page": 1
            }
            
            response = self.client.get(url, params=params)
            
            if response.status_code == 200:
                data = response.json()
                records = data.get("veterans", []) or data.get("results", []) or []
                
                for record in records[:max_results]:
                    first_name = record.get("firstName", "").strip().upper()
                    last_name = record.get("lastName", "").strip().upper()
                    branch = self._normalize_branch(record.get("branchOfService", ""))
                    birth_date = self._parse_date(record.get("birthDate", ""))
                    
                    if first_name and last_name and birth_date:
                        veterans.append({
                            "first_name": first_name,
                            "last_name": last_name,
                            "branch": branch,
                            "birth_date": birth_date,
                            "source": "VLM"
                        })
                
                logger.info(f"✅ Found {len(veterans)} veterans from VLM")
            
        except Exception as e:
            logger.error(f"VLM error: {e}")
        
        return veterans

    def scrape_all_sources(self, max_per_source: int = 10) -> List[Dict]:
        """Scrape from all available sources"""
        all_veterans = []
        
        # Random last names to search
        search_names = random.sample(SEARCH_LAST_NAMES, min(5, len(SEARCH_LAST_NAMES)))
        
        for last_name in search_names:
            # Try each source
            all_veterans.extend(self.scrape_va_grave_locator(last_name, max_per_source))
            all_veterans.extend(self.scrape_arlington_cemetery(last_name, max_per_source))
            all_veterans.extend(self.scrape_vlm(last_name, max_per_source))
        
        # Deduplicate
        seen = set()
        unique = []
        for v in all_veterans:
            key = f"{v['first_name']}|{v['last_name']}|{v['birth_date']}"
            if key not in seen:
                seen.add(key)
                unique.append(v)
        
        # Cache results
        self.scraped_cache = unique
        
        logger.info(f"📊 Total unique veterans scraped: {len(unique)}")
        return unique

    def get_fresh_veteran(self) -> Optional[Dict]:
        """
        Get a fresh veteran by scraping (not from cache)
        Tries multiple sources until finds unused data
        """
        # Try scraping with random last names
        for _ in range(3):
            last_name = random.choice(SEARCH_LAST_NAMES)
            
            # Try each source
            veterans = self.scrape_va_grave_locator(last_name, 10)
            if not veterans:
                veterans = self.scrape_arlington_cemetery(last_name, 10)
            if not veterans:
                veterans = self.scrape_vlm(last_name, 10)
            
            # Find unused one
            for v in veterans:
                key = f"{v['first_name']}|{v['last_name']}|{v['birth_date']}"
                if key not in self.used_data:
                    self.used_data.add(key)
                    # Add discharge date (recent past - 2020-2025)
                    discharge_year = random.randint(2020, 2025)
                    v["discharge_date"] = f"{discharge_year}-{random.randint(1,12):02d}-{random.randint(1,28):02d}"
                    return v
        
        return None

    def get_veteran_auto(self) -> Dict:
        """
        Automatically scrape and return veteran data
        First tries fresh scrape, falls back to cache, then static data
        """
        # Try fresh scrape
        veteran = self.get_fresh_veteran()
        if veteran:
            logger.info(f"🆕 Fresh scraped: {veteran['first_name']} {veteran['last_name']} ({veteran['source']})")
            return veteran
        
        # Try from cache
        if self.scraped_cache:
            for v in self.scraped_cache:
                key = f"{v['first_name']}|{v['last_name']}|{v['birth_date']}"
                if key not in self.used_data:
                    self.used_data.add(key)
                    discharge_year = random.randint(2020, 2025)
                    v["discharge_date"] = f"{discharge_year}-{random.randint(1,12):02d}-{random.randint(1,28):02d}"
                    logger.info(f"📦 From cache: {v['first_name']} {v['last_name']}")
                    return v
        
        # Fallback to static data
        logger.warning("⚠️ Using fallback static data")
        return get_fallback_veteran()


# Fallback static data - Modern veterans with valid age range (21-65 years)
# SheerID requires age between ~21-65 for military verification
# Using common American names with realistic birth dates (1961-2003)
FALLBACK_VETERANS = [
    # Recent Iraq/Afghanistan veterans (25-45 years old)
    {"first_name": "MICHAEL", "last_name": "JOHNSON", "branch": "Army", "birth_date": "1988-03-15"},
    {"first_name": "CHRISTOPHER", "last_name": "WILLIAMS", "branch": "Marine Corps", "birth_date": "1990-07-22"},
    {"first_name": "DAVID", "last_name": "BROWN", "branch": "Navy", "birth_date": "1985-11-08"},
    {"first_name": "JAMES", "last_name": "DAVIS", "branch": "Air Force", "birth_date": "1992-04-30"},
    {"first_name": "ROBERT", "last_name": "MILLER", "branch": "Army", "birth_date": "1987-09-12"},
    {"first_name": "DANIEL", "last_name": "WILSON", "branch": "Marine Corps", "birth_date": "1991-01-25"},
    {"first_name": "MATTHEW", "last_name": "MOORE", "branch": "Navy", "birth_date": "1989-06-17"},
    {"first_name": "JOSEPH", "last_name": "TAYLOR", "branch": "Coast Guard", "birth_date": "1986-12-03"},
    {"first_name": "ANDREW", "last_name": "ANDERSON", "branch": "Air Force", "birth_date": "1993-08-19"},
    {"first_name": "RYAN", "last_name": "THOMAS", "branch": "Army", "birth_date": "1984-02-28"},
    # Gulf War era veterans (45-60 years old)
    {"first_name": "WILLIAM", "last_name": "JACKSON", "branch": "Army", "birth_date": "1975-05-14"},
    {"first_name": "RICHARD", "last_name": "WHITE", "branch": "Marine Corps", "birth_date": "1972-10-21"},
    {"first_name": "THOMAS", "last_name": "HARRIS", "branch": "Navy", "birth_date": "1970-03-07"},
    {"first_name": "MARK", "last_name": "MARTIN", "branch": "Air Force", "birth_date": "1973-07-30"},
    {"first_name": "STEVEN", "last_name": "THOMPSON", "branch": "Army", "birth_date": "1968-11-11"},
    # Younger veterans (21-30 years old)
    {"first_name": "TYLER", "last_name": "GARCIA", "branch": "Marine Corps", "birth_date": "1998-04-05"},
    {"first_name": "BRANDON", "last_name": "MARTINEZ", "branch": "Army", "birth_date": "1999-08-23"},
    {"first_name": "JACOB", "last_name": "ROBINSON", "branch": "Navy", "birth_date": "1997-12-10"},
    {"first_name": "NICHOLAS", "last_name": "CLARK", "branch": "Air Force", "birth_date": "2000-02-14"},
    {"first_name": "JOSHUA", "last_name": "LEWIS", "branch": "Coast Guard", "birth_date": "1996-06-28"},
]

_used_fallback = set()
_used_generated = set()

def get_fallback_veteran() -> Dict:
    """Get fallback veteran data from static list"""
    global _used_fallback
    
    for v in FALLBACK_VETERANS:
        key = f"{v['first_name']}|{v['last_name']}"
        if key not in _used_fallback:
            _used_fallback.add(key)
            result = v.copy()
            # Recent discharge (2020-2025)
            discharge_year = random.randint(2020, 2025)
            result["discharge_date"] = f"{discharge_year}-{random.randint(1,12):02d}-{random.randint(1,28):02d}"
            result["source"] = "FALLBACK"
            return result
    
    # All used, generate new realistic data
    logger.info("📊 Static fallback exhausted, generating realistic data...")
    return get_generated_veteran()


def get_generated_veteran() -> Dict:
    """Generate new realistic veteran data using demographics"""
    global _used_generated
    
    max_attempts = 50
    for _ in range(max_attempts):
        veteran = RealisticVeteranGenerator.generate()
        key = f"{veteran['first_name']}|{veteran['last_name']}|{veteran['birth_date']}"
        
        if key not in _used_generated:
            # Validate before using
            is_valid, errors, warnings = DataQualityValidator.validate(veteran)
            
            if is_valid:
                _used_generated.add(key)
                score = DataQualityValidator.score_data(veteran)
                logger.info(f"🎲 Generated: {veteran['first_name']} {veteran['last_name']} (Score: {score}/100)")
                return veteran
            else:
                logger.debug(f"Generated data failed validation: {errors}")
    
    # Last resort - return any generated data
    veteran = RealisticVeteranGenerator.generate()
    veteran["source"] = "GENERATED_UNVALIDATED"
    return veteran


def get_best_veteran_data(preferred_branch: str = None) -> Dict:
    """
    Get the best available veteran data
    Priority: Scraped > Fallback > Generated
    """
    scraper = get_scraper()
    
    # Try scraping first
    veteran = scraper.get_fresh_veteran()
    if veteran:
        is_valid, errors, _ = DataQualityValidator.validate(veteran)
        if is_valid:
            score = DataQualityValidator.score_data(veteran)
            if score >= 60:
                logger.info(f"✅ Using scraped data (Score: {score})")
                return veteran
    
    # Try fallback
    veteran = get_fallback_veteran()
    is_valid, errors, _ = DataQualityValidator.validate(veteran)
    if is_valid:
        score = DataQualityValidator.score_data(veteran)
        if score >= 50:
            logger.info(f"✅ Using fallback data (Score: {score})")
            return veteran
    
    # Generate new data
    for _ in range(5):
        veteran = get_generated_veteran()
        if preferred_branch and veteran.get("branch") != preferred_branch:
            continue
        
        score = DataQualityValidator.score_data(veteran)
        if score >= 70:
            logger.info(f"✅ Using generated data (Score: {score})")
            return veteran
    
    # Return whatever we have
    return veteran


# ============== REALISTIC VETERAN DATA GENERATOR ==============

class RealisticVeteranGenerator:
    """Generate synthetic veteran data based on real military demographics"""
    
    @staticmethod
    def select_branch_weighted() -> str:
        """Select branch based on actual military distribution"""
        branches = list(BRANCH_DISTRIBUTION.keys())
        weights = list(BRANCH_DISTRIBUTION.values())
        return random.choices(branches, weights=weights)[0]
    
    @staticmethod
    def select_age_weighted() -> int:
        """Select age based on veteran verification demographics"""
        age_ranges = list(AGE_DISTRIBUTION.keys())
        weights = list(AGE_DISTRIBUTION.values())
        selected_range = random.choices(age_ranges, weights=weights)[0]
        return random.randint(selected_range[0], selected_range[1])
    
    @staticmethod
    def select_era_weighted() -> Dict:
        """Select veteran era based on verification patterns"""
        eras = VETERAN_TEMPLATES
        weights = [t["weight"] for t in eras]
        return random.choices(eras, weights=weights)[0]
    
    @classmethod
    def generate(cls) -> Dict:
        """Generate demographically accurate veteran data"""
        current_year = datetime.now().year
        
        # Select era first (determines age range and branch likelihood)
        era = cls.select_era_weighted()
        
        # Select age within era's range
        age = random.randint(era["age_range"][0], era["age_range"][1])
        birth_year = current_year - age
        
        # Select branch (prefer era's common branches)
        if random.random() < 0.7:  # 70% chance to use era-specific branch
            branch = random.choice(era["common_branches"])
        else:
            branch = cls.select_branch_weighted()
        
        # Generate birth date
        birth_month = random.randint(1, 12)
        birth_day = random.randint(1, 28)
        birth_date = f"{birth_year}-{birth_month:02d}-{birth_day:02d}"
        
        # Generate service dates
        enlist_age = random.randint(18, 25)
        service_start = birth_year + enlist_age
        service_length = random.randint(4, 20)
        service_end = min(service_start + service_length, current_year - 1)
        
        # Discharge date (recent for better success)
        discharge_year = random.randint(max(2018, service_end - 2), min(2025, service_end + 1))
        discharge_month = random.randint(1, 12)
        discharge_day = random.randint(1, 28)
        discharge_date = f"{discharge_year}-{discharge_month:02d}-{discharge_day:02d}"
        
        return {
            "first_name": random.choice(FIRST_NAMES_MALE),
            "last_name": random.choice(LAST_NAMES),
            "birth_date": birth_date,
            "branch": branch,
            "discharge_date": discharge_date,
            "era": era["era"],
            "age": age,
            "service_start": service_start,
            "service_end": service_end,
            "mos": random.choice(MOS_BY_BRANCH.get(branch, ["N/A"])),
            "source": "GENERATED"
        }


class DataQualityValidator:
    """Validate veteran data for realism and SheerID acceptance"""
    
    # SheerID age limits
    MIN_AGE = 18
    MAX_AGE = 90
    OPTIMAL_MIN_AGE = 21
    OPTIMAL_MAX_AGE = 65
    
    @classmethod
    def validate(cls, data: Dict) -> tuple:
        """
        Validate veteran data
        Returns: (is_valid, errors, warnings)
        """
        errors = []
        warnings = []
        current_year = datetime.now().year
        
        # Extract birth year
        try:
            birth_year = int(data['birth_date'].split('-')[0])
            age = current_year - birth_year
        except (KeyError, ValueError, IndexError):
            errors.append("Invalid or missing birth_date")
            age = 0
        
        # Age validation
        if age < cls.MIN_AGE:
            errors.append(f"Age {age} below minimum ({cls.MIN_AGE})")
        elif age > cls.MAX_AGE:
            errors.append(f"Age {age} above maximum ({cls.MAX_AGE})")
        elif age < cls.OPTIMAL_MIN_AGE:
            warnings.append(f"Age {age} below optimal ({cls.OPTIMAL_MIN_AGE})")
        elif age > cls.OPTIMAL_MAX_AGE:
            warnings.append(f"Age {age} above optimal ({cls.OPTIMAL_MAX_AGE})")
        
        # Branch validation
        valid_branches = list(BRANCH_DISTRIBUTION.keys())
        branch = data.get('branch', '')
        if branch not in valid_branches:
            errors.append(f"Invalid branch: {branch}")
        
        # Name validation
        first_name = data.get('first_name', '')
        last_name = data.get('last_name', '')
        if len(first_name) < 2:
            errors.append("First name too short")
        if len(last_name) < 2:
            errors.append("Last name too short")
        if not first_name.isalpha():
            warnings.append("First name contains non-alpha characters")
        if not last_name.replace("-", "").replace("'", "").isalpha():
            warnings.append("Last name contains unusual characters")
        
        # Discharge date validation
        discharge_date = data.get('discharge_date', '')
        if discharge_date:
            try:
                discharge_year = int(discharge_date.split('-')[0])
                if discharge_year > current_year:
                    warnings.append(f"Discharge year {discharge_year} is in the future")
                if discharge_year < birth_year + 18:
                    errors.append("Discharge before age 18")
            except (ValueError, IndexError):
                warnings.append("Could not parse discharge date")
        
        is_valid = len(errors) == 0
        return is_valid, errors, warnings
    
    @classmethod
    def score_data(cls, data: Dict) -> int:
        """
        Score data quality (0-100)
        Higher = more likely to be accepted
        """
        score = 100
        is_valid, errors, warnings = cls.validate(data)
        
        # Deduct for errors
        score -= len(errors) * 25
        
        # Deduct for warnings
        score -= len(warnings) * 10
        
        # Bonus for optimal age range
        current_year = datetime.now().year
        try:
            birth_year = int(data['birth_date'].split('-')[0])
            age = current_year - birth_year
            if 25 <= age <= 55:  # Prime verification age
                score += 10
        except:
            pass
        
        # Bonus for common branches
        branch = data.get('branch', '')
        if branch in ['Army', 'Marine Corps', 'Navy']:
            score += 5
        
        return max(0, min(100, score))


# Global scraper instance
_scraper = None

def get_scraper() -> VeteranDataScraper:
    """Get or create scraper instance"""
    global _scraper
    if _scraper is None:
        _scraper = VeteranDataScraper()
    return _scraper


def get_real_veteran_data(branch: str = None) -> Dict:
    """
    Get real veteran data by auto-scraping
    """
    scraper = get_scraper()
    veteran = scraper.get_veteran_auto()
    
    if branch and veteran.get("branch") != branch:
        # Try to find matching branch
        for _ in range(3):
            v = scraper.get_veteran_auto()
            if v.get("branch") == branch:
                return v
    
    return veteran


def get_veteran_for_verification() -> Dict:
    """
    Get complete veteran data ready for SheerID verification
    Auto-scrapes from public sources
    """
    return get_real_veteran_data()


# Quick test
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("=" * 60)
    print("Testing Veteran Data System")
    print("=" * 60)
    
    # Test realistic generator
    print("\n🎲 Testing Realistic Generator...")
    for i in range(3):
        veteran = RealisticVeteranGenerator.generate()
        is_valid, errors, warnings = DataQualityValidator.validate(veteran)
        score = DataQualityValidator.score_data(veteran)
        
        print(f"\n{i+1}. {veteran['first_name']} {veteran['last_name']}")
        print(f"   Branch: {veteran['branch']} | Era: {veteran.get('era', 'N/A')}")
        print(f"   Birth: {veteran['birth_date']} (Age: {veteran.get('age', 'N/A')})")
        print(f"   Discharge: {veteran['discharge_date']}")
        print(f"   Valid: {'✅' if is_valid else '❌'} | Score: {score}/100")
        if errors:
            print(f"   Errors: {errors}")
        if warnings:
            print(f"   Warnings: {warnings}")
    
    # Test scraper
    print("\n" + "=" * 60)
    print("🔍 Testing Auto-Scraper...")
    scraper = VeteranDataScraper()
    
    for i in range(3):
        veteran = scraper.get_veteran_auto()
        score = DataQualityValidator.score_data(veteran)
        print(f"\n{i+1}. {veteran['first_name']} {veteran['last_name']}")
        print(f"   Branch: {veteran['branch']}")
        print(f"   Birth: {veteran['birth_date']}")
        print(f"   Discharge: {veteran['discharge_date']}")
        print(f"   Source: {veteran.get('source', 'N/A')} | Score: {score}/100")
    
    # Test best veteran selector
    print("\n" + "=" * 60)
    print("🏆 Testing Best Veteran Selector...")
    veteran = get_best_veteran_data()
    score = DataQualityValidator.score_data(veteran)
    print(f"\nBest: {veteran['first_name']} {veteran['last_name']}")
    print(f"   Branch: {veteran['branch']}")
    print(f"   Birth: {veteran['birth_date']}")
    print(f"   Source: {veteran.get('source', 'N/A')} | Score: {score}/100")
