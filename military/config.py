# Military SheerID Verification Configuration

# SheerID API Configuration
SHEERID_BASE_URL = 'https://services.sheerid.com'
MY_SHEERID_URL = 'https://my.sheerid.com'

# File Size Limit
MAX_FILE_SIZE = 1 * 1024 * 1024  # 1MB

# Military Status Options
MILITARY_STATUS = ['VETERAN', 'ACTIVE_DUTY', 'RESERVIST']

# Military Organizations
ORGANIZATIONS = {
    '4070': {
        'id': 4070,
        'idExtended': '4070',
        'name': 'Army',
        'country': 'US',
        'type': 'MILITARY'
    },
    '4073': {
        'id': 4073,
        'idExtended': '4073',
        'name': 'Air Force',
        'country': 'US',
        'type': 'MILITARY'
    },
    '4072': {
        'id': 4072,
        'idExtended': '4072',
        'name': 'Navy',
        'country': 'US',
        'type': 'MILITARY'
    },
    '4071': {
        'id': 4071,
        'idExtended': '4071',
        'name': 'Marine Corps',
        'country': 'US',
        'type': 'MILITARY'
    },
    '4074': {
        'id': 4074,
        'idExtended': '4074',
        'name': 'Coast Guard',
        'country': 'US',
        'type': 'MILITARY'
    },
    '4544268': {
        'id': 4544268,
        'idExtended': '4544268',
        'name': 'Space Force',
        'country': 'US',
        'type': 'MILITARY'
    }
}

# Default Organization
DEFAULT_ORG_ID = '4070'  # Army
