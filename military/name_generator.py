"""Random Name Generator for Military Verification"""
import random
from datetime import datetime, timedelta


class NameGenerator:
    """English Name Generator"""
    
    FIRST_NAMES = [
        'James', 'John', 'Robert', 'Michael', 'William', 'David', 'Richard', 'Joseph',
        'Thomas', 'Charles', 'Christopher', 'Daniel', 'Matthew', 'Anthony', 'Mark',
        'Donald', 'Steven', 'Paul', 'Andrew', 'Joshua', 'Kenneth', 'Kevin', 'Brian',
        'George', 'Timothy', 'Ronald', 'Edward', 'Jason', 'Jeffrey', 'Ryan'
    ]
    
    LAST_NAMES = [
        'Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis',
        'Rodriguez', 'Martinez', 'Hernandez', 'Lopez', 'Gonzalez', 'Wilson', 'Anderson',
        'Thomas', 'Taylor', 'Moore', 'Jackson', 'Martin', 'Lee', 'Perez', 'Thompson',
        'White', 'Harris', 'Sanchez', 'Clark', 'Ramirez', 'Lewis', 'Robinson'
    ]
    
    @classmethod
    def generate(cls):
        """
        Generate random English name
        
        Returns:
            dict: Contains first_name, last_name, full_name
        """
        first_name = random.choice(cls.FIRST_NAMES)
        last_name = random.choice(cls.LAST_NAMES)
        
        return {
            'first_name': first_name,
            'last_name': last_name,
            'full_name': f"{first_name} {last_name}"
        }


def generate_email(domain='gmail.com'):
    """
    Generate random email address
    
    Args:
        domain: Email domain
    
    Returns:
        str: Email address
    """
    chars = 'abcdefghijklmnopqrstuvwxyz0123456789'
    username = ''.join(random.choice(chars) for _ in range(10))
    return f"{username}@{domain}"


def generate_birth_date(min_age=25, max_age=55):
    """
    Generate random birth date for veteran
    
    Args:
        min_age: Minimum age
        max_age: Maximum age
    
    Returns:
        str: Birth date in YYYY-MM-DD format
    """
    today = datetime.now()
    min_date = today - timedelta(days=max_age * 365)
    max_date = today - timedelta(days=min_age * 365)
    
    random_days = random.randint(0, (max_date - min_date).days)
    birth_date = min_date + timedelta(days=random_days)
    
    return birth_date.strftime('%Y-%m-%d')


def generate_discharge_date(min_years_ago=1, max_years_ago=10):
    """
    Generate random discharge date for veteran
    
    Args:
        min_years_ago: Minimum years since discharge
        max_years_ago: Maximum years since discharge
    
    Returns:
        str: Discharge date in YYYY-MM-DD format
    """
    today = datetime.now()
    min_date = today - timedelta(days=max_years_ago * 365)
    max_date = today - timedelta(days=min_years_ago * 365)
    
    random_days = random.randint(0, (max_date - min_date).days)
    discharge_date = min_date + timedelta(days=random_days)
    
    return discharge_date.strftime('%Y-%m-%d')
