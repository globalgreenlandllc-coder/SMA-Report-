"""
sample_comps.py -- Sample data standing in for a live RESO feed.

This is the ONLY module that knows about specific properties. Every field uses
RESO Data Dictionary names, so swapping this file for a live SimplyRETS / MLSGrid
/ Trestle loader that yields the same shape is a single-file change -- the engine
and report never need to know where the data came from.

Setting: a fictional neighborhood in Austin, TX. One comp (the lakeside luxury
flip, MLS A-1007) is a deliberate outlier so the engine's outlier handling is
visible end-to-end.
"""

# The property being valued.
SUBJECT = {
    "ListingId": "SUBJECT",
    "UnparsedAddress": "1420 Meadowlark Ln, Austin, TX 78745",
    "LivingArea": 2150,            # sqft
    "BedroomsTotal": 4,
    "BathroomsTotalInteger": 3,
    "GarageSpaces": 2,
    "PoolPrivateYN": False,
    "YearBuilt": 2006,
    "LotSizeSquareFeet": 8200,
    "Latitude": 30.2180,
    "Longitude": -97.8000,
    # Upgrades the agent recorded (used later by the what-if simulator).
    "Upgrades": ["Renovated kitchen (2023)", "New roof (2022)"],
}

# Comparable listings: a mix of recent closed sales and current active listings.
COMPS = [
    {
        "ListingId": "A-1001",
        "ListingUrl": "https://sandbox.simplyrets.com/listing/A-1001",
        "ListOfficeName": "Lone Star Realty Group",
        "StandardStatus": "Closed",
        "ClosePrice": 565000,
        "ListPrice": 575000,
        "CloseDate": "2026-04-22",
        "UnparsedAddress": "1508 Meadowlark Ln, Austin, TX 78745",
        "LivingArea": 2210,
        "BedroomsTotal": 4,
        "BathroomsTotalInteger": 3,
        "GarageSpaces": 2,
        "PoolPrivateYN": False,
        "YearBuilt": 2007,
        "Latitude": 30.2188,
        "Longitude": -97.8012,
    },
    {
        "ListingId": "A-1002",
        "ListingUrl": "https://sandbox.simplyrets.com/listing/A-1002",
        "ListOfficeName": "Hill Country Homes",
        "StandardStatus": "Closed",
        "ClosePrice": 540000,
        "ListPrice": 549000,
        "CloseDate": "2026-03-10",
        "UnparsedAddress": "907 Bluebird Dr, Austin, TX 78745",
        "LivingArea": 2050,
        "BedroomsTotal": 4,
        "BathroomsTotalInteger": 2,
        "GarageSpaces": 2,
        "PoolPrivateYN": False,
        "YearBuilt": 2004,
        "Latitude": 30.2150,
        "Longitude": -97.7975,
    },
    {
        "ListingId": "A-1003",
        "ListingUrl": "https://sandbox.simplyrets.com/listing/A-1003",
        "ListOfficeName": "Capitol City Properties",
        "StandardStatus": "Closed",
        "ClosePrice": 612000,
        "ListPrice": 599000,
        "CloseDate": "2026-05-05",
        "UnparsedAddress": "2201 Robin St, Austin, TX 78745",
        "LivingArea": 2380,
        "BedroomsTotal": 4,
        "BathroomsTotalInteger": 3,
        "GarageSpaces": 2,
        "PoolPrivateYN": True,
        "YearBuilt": 2010,
        "Latitude": 30.2205,
        "Longitude": -97.8041,
    },
    {
        "ListingId": "A-1004",
        "ListingUrl": "https://sandbox.simplyrets.com/listing/A-1004",
        "ListOfficeName": "Lone Star Realty Group",
        "StandardStatus": "Closed",
        "ClosePrice": 498000,
        "ListPrice": 510000,
        "CloseDate": "2026-02-18",
        "UnparsedAddress": "612 Sparrow Ct, Austin, TX 78745",
        "LivingArea": 1880,
        "BedroomsTotal": 3,
        "BathroomsTotalInteger": 2,
        "GarageSpaces": 2,
        "PoolPrivateYN": False,
        "YearBuilt": 2001,
        "Latitude": 30.2129,
        "Longitude": -97.7948,
    },
    {
        "ListingId": "A-1005",
        "ListingUrl": "https://sandbox.simplyrets.com/listing/A-1005",
        "ListOfficeName": "Barton Creek Realty",
        "StandardStatus": "Closed",
        "ClosePrice": 588000,
        "ListPrice": 585000,
        "CloseDate": "2026-05-28",
        "UnparsedAddress": "1333 Meadowlark Ln, Austin, TX 78745",
        "LivingArea": 2260,
        "BedroomsTotal": 4,
        "BathroomsTotalInteger": 3,
        "GarageSpaces": 3,
        "PoolPrivateYN": False,
        "YearBuilt": 2008,
        "Latitude": 30.2176,
        "Longitude": -97.7989,
    },
    {
        "ListingId": "A-1006",
        "ListingUrl": "https://sandbox.simplyrets.com/listing/A-1006",
        "ListOfficeName": "Hill Country Homes",
        "StandardStatus": "Active",
        "ListPrice": 619000,
        "CloseDate": None,
        "UnparsedAddress": "1810 Cardinal Way, Austin, TX 78745",
        "LivingArea": 2300,
        "BedroomsTotal": 4,
        "BathroomsTotalInteger": 3,
        "GarageSpaces": 2,
        "PoolPrivateYN": False,
        "YearBuilt": 2009,
        "Latitude": 30.2199,
        "Longitude": -97.8025,
    },
    {
        # Deliberate outlier: a luxury lakeside flip ~3 miles away. The engine
        # should flag and down-weight this rather than let it drag the estimate.
        "ListingId": "A-1007",
        "ListingUrl": "https://sandbox.simplyrets.com/listing/A-1007",
        "ListOfficeName": "Lakeway Luxury Group",
        "StandardStatus": "Closed",
        "ClosePrice": 1150000,
        "ListPrice": 1195000,
        "CloseDate": "2026-04-01",
        "UnparsedAddress": "55 Lakeshore Dr, Austin, TX 78734",
        "LivingArea": 2400,
        "BedroomsTotal": 4,
        "BathroomsTotalInteger": 4,
        "GarageSpaces": 3,
        "PoolPrivateYN": True,
        "YearBuilt": 2021,
        "Latitude": 30.3650,
        "Longitude": -97.9780,
    },
]

# Agent branding -- uploaded once, applied to every report.
AGENT_BRANDING = {
    "agent_name": "Jordan Avery",
    "title": "REALTOR(R), ABR",
    "brokerage": "Lone Star Realty Group",
    "phone": "(512) 555-0142",
    "email": "jordan@lonestarrealty.example",
    "license": "TX #0654321",
    "logo_url": "",            # path/URL to a logo image (optional)
    "headshot_url": "",        # path/URL to a headshot (optional)
    "primary_color": "#1f6feb",
    "accent_color": "#0b3d91",
}
