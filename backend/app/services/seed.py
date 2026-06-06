"""Seed data - Initialize teams, groups, and matches from FIFA 2026 data"""
import logging
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.match import Team, Match

logger = logging.getLogger(__name__)

# FIFA 2026 Official Groups (December 2025 draw)
OFFICIAL_GROUPS = {
    "A": ["MEX", "RSA", "KOR", "CZE"],
    "B": ["CAN", "BIH", "QAT", "SUI"],
    "C": ["BRA", "MAR", "HAI", "SCO"],
    "D": ["USA", "PAR", "AUS", "TUR"],
    "E": ["GER", "CUW", "CIV", "ECU"],
    "F": ["NED", "JPN", "SWE", "TUN"],
    "G": ["BEL", "EGY", "IRN", "NZL"],
    "H": ["ESP", "CPV", "KSA", "URU"],
    "I": ["FRA", "SEN", "IRQ", "NOR"],
    "J": ["ARG", "ALG", "AUT", "JOR"],
    "K": ["POR", "COD", "UZB", "COL"],
    "L": ["ENG", "CRO", "GHA", "PAN"],
}

TEAMS_DATA = {
    "USA": {"name": "美国", "nameEn": "United States", "flag": "🇺🇸", "conf": "CONCACAF", "rank": 14, "strength": 82},
    "MEX": {"name": "墨西哥", "nameEn": "Mexico", "flag": "🇲🇽", "conf": "CONCACAF", "rank": 15, "strength": 78},
    "CAN": {"name": "加拿大", "nameEn": "Canada", "flag": "🇨🇦", "conf": "CONCACAF", "rank": 27, "strength": 68},
    "ESP": {"name": "西班牙", "nameEn": "Spain", "flag": "🇪🇸", "conf": "UEFA", "rank": 1, "strength": 92},
    "ARG": {"name": "阿根廷", "nameEn": "Argentina", "flag": "🇦🇷", "conf": "CONMEBOL", "rank": 2, "strength": 91},
    "FRA": {"name": "法国", "nameEn": "France", "flag": "🇫🇷", "conf": "UEFA", "rank": 3, "strength": 90},
    "ENG": {"name": "英格兰", "nameEn": "England", "flag": "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "conf": "UEFA", "rank": 4, "strength": 89},
    "BRA": {"name": "巴西", "nameEn": "Brazil", "flag": "🇧🇷", "conf": "CONMEBOL", "rank": 5, "strength": 88},
    "POR": {"name": "葡萄牙", "nameEn": "Portugal", "flag": "🇵🇹", "conf": "UEFA", "rank": 6, "strength": 86},
    "NED": {"name": "荷兰", "nameEn": "Netherlands", "flag": "🇳🇱", "conf": "UEFA", "rank": 7, "strength": 85},
    "BEL": {"name": "比利时", "nameEn": "Belgium", "flag": "🇧🇪", "conf": "UEFA", "rank": 8, "strength": 83},
    "GER": {"name": "德国", "nameEn": "Germany", "flag": "🇩🇪", "conf": "UEFA", "rank": 9, "strength": 84},
    "CRO": {"name": "克罗地亚", "nameEn": "Croatia", "flag": "🇭🇷", "conf": "UEFA", "rank": 10, "strength": 80},
    "MAR": {"name": "摩洛哥", "nameEn": "Morocco", "flag": "🇲🇦", "conf": "CAF", "rank": 11, "strength": 79},
    "COL": {"name": "哥伦比亚", "nameEn": "Colombia", "flag": "🇨🇴", "conf": "CONMEBOL", "rank": 13, "strength": 77},
    "URU": {"name": "乌拉圭", "nameEn": "Uruguay", "flag": "🇺🇾", "conf": "CONMEBOL", "rank": 16, "strength": 76},
    "SUI": {"name": "瑞士", "nameEn": "Switzerland", "flag": "🇨🇭", "conf": "UEFA", "rank": 17, "strength": 75},
    "JPN": {"name": "日本", "nameEn": "Japan", "flag": "🇯🇵", "conf": "AFC", "rank": 18, "strength": 76},
    "SEN": {"name": "塞内加尔", "nameEn": "Senegal", "flag": "🇸🇳", "conf": "CAF", "rank": 19, "strength": 74},
    "IRN": {"name": "伊朗", "nameEn": "Iran", "flag": "🇮🇷", "conf": "AFC", "rank": 20, "strength": 71},
    "KOR": {"name": "韩国", "nameEn": "South Korea", "flag": "🇰🇷", "conf": "AFC", "rank": 22, "strength": 70},
    "ECU": {"name": "厄瓜多尔", "nameEn": "Ecuador", "flag": "🇪🇨", "conf": "CONMEBOL", "rank": 23, "strength": 69},
    "AUT": {"name": "奥地利", "nameEn": "Austria", "flag": "🇦🇹", "conf": "UEFA", "rank": 24, "strength": 72},
    "SWE": {"name": "瑞典", "nameEn": "Sweden", "flag": "🇸🇪", "conf": "UEFA", "rank": 25, "strength": 68},
    "AUS": {"name": "澳大利亚", "nameEn": "Australia", "flag": "🇦🇺", "conf": "AFC", "rank": 26, "strength": 67},
    "NOR": {"name": "挪威", "nameEn": "Norway", "flag": "🇳🇴", "conf": "UEFA", "rank": 29, "strength": 68},
    "TUR": {"name": "土耳其", "nameEn": "Turkey", "flag": "🇹🇷", "conf": "UEFA", "rank": 28, "strength": 70},
    "PAN": {"name": "巴拿马", "nameEn": "Panama", "flag": "🇵🇦", "conf": "CONCACAF", "rank": 30, "strength": 60},
    "EGY": {"name": "埃及", "nameEn": "Egypt", "flag": "🇪🇬", "conf": "CAF", "rank": 34, "strength": 66},
    "ALG": {"name": "阿尔及利亚", "nameEn": "Algeria", "flag": "🇩🇿", "conf": "CAF", "rank": 35, "strength": 65},
    "SCO": {"name": "苏格兰", "nameEn": "Scotland", "flag": "🏴󠁧󠁢󠁳󠁣󠁴󠁿", "conf": "UEFA", "rank": 36, "strength": 64},
    "PAR": {"name": "巴拉圭", "nameEn": "Paraguay", "flag": "🇵🇾", "conf": "CONMEBOL", "rank": 39, "strength": 63},
    "TUN": {"name": "突尼斯", "nameEn": "Tunisia", "flag": "🇹🇳", "conf": "CAF", "rank": 40, "strength": 64},
    "BIH": {"name": "波黑", "nameEn": "Bosnia Herzegovina", "flag": "🇧🇦", "conf": "UEFA", "rank": 32, "strength": 62},
    "CZE": {"name": "捷克", "nameEn": "Czech Republic", "flag": "🇨🇿", "conf": "UEFA", "rank": 33, "strength": 63},
    "CIV": {"name": "科特迪瓦", "nameEn": "Ivory Coast", "flag": "🇨🇮", "conf": "CAF", "rank": 42, "strength": 65},
    "GHA": {"name": "加纳", "nameEn": "Ghana", "flag": "🇬🇭", "conf": "CAF", "rank": 72, "strength": 62},
    "UZB": {"name": "乌兹别克斯坦", "nameEn": "Uzbekistan", "flag": "🇺🇿", "conf": "AFC", "rank": 50, "strength": 60},
    "QAT": {"name": "卡塔尔", "nameEn": "Qatar", "flag": "🇶🇦", "conf": "AFC", "rank": 51, "strength": 58},
    "KSA": {"name": "沙特", "nameEn": "Saudi Arabia", "flag": "🇸🇦", "conf": "AFC", "rank": 60, "strength": 58},
    "RSA": {"name": "南非", "nameEn": "South Africa", "flag": "🇿🇦", "conf": "CAF", "rank": 61, "strength": 56},
    "JOR": {"name": "约旦", "nameEn": "Jordan", "flag": "🇯🇴", "conf": "AFC", "rank": 66, "strength": 55},
    "CPV": {"name": "佛德角", "nameEn": "Cape Verde", "flag": "🇨🇻", "conf": "CAF", "rank": 68, "strength": 55},
    "CUW": {"name": "库拉索", "nameEn": "Curacao", "flag": "🇨🇼", "conf": "CONCACAF", "rank": 82, "strength": 52},
    "HAI": {"name": "海地", "nameEn": "Haiti", "flag": "🇭🇹", "conf": "CONCACAF", "rank": 84, "strength": 50},
    "NZL": {"name": "新西兰", "nameEn": "New Zealand", "flag": "🇳🇿", "conf": "OFC", "rank": 86, "strength": 54},
    "IRQ": {"name": "伊拉克", "nameEn": "Iraq", "flag": "🇮🇶", "conf": "AFC", "rank": 65, "strength": 58},
    "COD": {"name": "刚果民主", "nameEn": "DR Congo", "flag": "🇨🇩", "conf": "CAF", "rank": 70, "strength": 56},
}

VENUES = [
    ("MetLife Stadium", "New York/New Jersey"),
    ("SoFi Stadium", "Los Angeles"),
    ("AT&T Stadium", "Dallas"),
    ("Mercedes-Benz Stadium", "Atlanta"),
    ("Levi's Stadium", "San Francisco"),
    ("Arrowhead Stadium", "Kansas City"),
    ("Lumen Field", "Seattle"),
    ("Gillette Stadium", "Boston"),
    ("BC Place", "Vancouver"),
    ("Rogers Centre", "Toronto"),
    ("BMO Field", "Toronto"),
    ("Estadio Azteca", "Mexico City"),
    ("Estadio BBVA", "Monterrey"),
]


async def seed_database(db: AsyncSession):
    """Seed teams, groups, and matches"""
    # Check if already seeded
    count = (await db.execute(select(func.count()).select_from(Team))).scalar()
    if count and count > 0:
        logger.info(f"Database already has {count} teams, skipping seed")
        return

    logger.info("🌱 Seeding database with FIFA 2026 data...")

    # Insert teams
    for code, data in TEAMS_DATA.items():
        team = Team(
            code=code,
            name=data["name"],
            name_en=data["nameEn"],
            flag=data["flag"],
            confederation=data["conf"],
            fifa_rank=data["rank"],
            strength=data["strength"],
        )
        db.add(team)

    await db.flush()
    logger.info(f"  ✅ {len(TEAMS_DATA)} teams inserted")

    # Insert group stage matches
    import random
    venue_idx = 0
    for group, teams in OFFICIAL_GROUPS.items():
        t1, t2, t3, t4 = teams
        matchups = [
            (t1, t2, 1), (t3, t4, 1),
            (t1, t3, 2), (t2, t4, 2),
            (t1, t4, 3), (t2, t3, 3),
        ]
        for home, away, round_num in matchups:
            venue, city = VENUES[venue_idx % len(VENUES)]
            venue_idx += 1
            match = Match(
                stage="group",
                group_name=group,
                round_num=round_num,
                home_team_code=home,
                away_team_code=away,
                venue=venue,
                city=city,
                status="scheduled",
            )
            db.add(match)

    # Insert knockout stage placeholders
    knockout_stages = [
        ("R32", 16), ("R16", 8), ("QF", 4), ("SF", 2), ("3RD", 1), ("FINAL", 1),
    ]
    for stage, count in knockout_stages:
        for _ in range(count):
            venue, city = VENUES[random.randint(0, len(VENUES) - 1)]
            match = Match(
                stage=stage,
                group_name=None,
                home_team_code=None,
                away_team_code=None,
                venue=venue,
                city=city,
                status="scheduled",
            )
            db.add(match)

    await db.commit()
    total = (await db.execute(select(func.count()).select_from(Match))).scalar()
    logger.info(f"  ✅ {total} matches inserted (72 group + {total-72} knockout)")
