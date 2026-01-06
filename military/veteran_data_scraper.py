"""
Veteran Data Scraper
Scrapes real veteran data from official public sources for SheerID verification
Auto-scrapes from VA Grave Locator, CMOHS, and other public memorial sites
"""
import random
import httpx
import re
import logging
import json
from typing import Dict, List, Optional
from datetime import datetime
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Common American last names for searching
SEARCH_LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
    "Rodriguez", "Martinez", "Hernandez", "Lopez", "Wilson", "Anderson", "Thomas",
    "Taylor", "Moore", "Jackson", "Martin", "Lee", "Thompson", "White", "Harris",
    "Clark", "Lewis", "Robinson", "Walker", "Hall", "Allen", "Young", "King",
    "Wright", "Scott", "Green", "Baker", "Adams", "Nelson", "Hill", "Campbell"
]

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

def get_fallback_veteran() -> Dict:
    """Get fallback veteran data"""
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
    
    # All used, return random
    v = random.choice(FALLBACK_VETERANS).copy()
    discharge_year = random.randint(2020, 2025)
    v["discharge_date"] = f"{discharge_year}-{random.randint(1,12):02d}-{random.randint(1,28):02d}"
    v["source"] = "FALLBACK"
    return v


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
    print("Testing Veteran Data Auto-Scraper")
    print("=" * 60)
    
    scraper = VeteranDataScraper()
    
    # Test scraping
    print("\n🔍 Testing auto-scrape...")
    for i in range(3):
        veteran = scraper.get_veteran_auto()
        print(f"\n{i+1}. {veteran['first_name']} {veteran['last_name']}")
        print(f"   Branch: {veteran['branch']}")
        print(f"   Birth: {veteran['birth_date']}")
        print(f"   Discharge: {veteran['discharge_date']}")
        print(f"   Source: {veteran.get('source', 'N/A')}")
