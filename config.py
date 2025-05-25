#!/usr/bin/env python3
"""
Newsletter System v07 - Configuration Module

Contains all configuration settings for the newsletter system including:
- Environment variables
- Directory paths
- Color schemes
- Logging setup
- RSS feeds and trusted senders lists

Author: Max Polwin
"""

import os
import logging
import sys
#import importlib
#from pathlib import Path

# This will define the missing function that's needed to retrieve your required environment variables.
class ConfigError(Exception):
    """Custom exception for configuration errors."""
    pass

def get_required_env_var(var_name):
    """
    Get a required environment variable or raise an error.

    Args:
        var_name: Name of the environment variable

    Returns:
        The value of the environment variable

    Raises:
        ConfigError: If the environment variable is not set
    """
    value = os.getenv(var_name)
    if not value:
        raise ConfigError(f"Required environment variable '{var_name}' is not set")
    return value

# Define base directory for all paths
# Can be overridden by setting the ESG_BASE_DIR environment variable
BASE_DIR = os.getenv('ESG_BASE_DIR', os.path.dirname(os.path.abspath(__file__)))

def load_env_vars():
    """Load environment variables from .env file manually."""
    env_path = os.path.join(BASE_DIR, '.env')
    try:
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                key, value = line.split('=', 1)
                os.environ[key.strip()] = value.strip().strip('"\'')
        print(f"Loaded environment variables from {env_path}")
    except FileNotFoundError:
        print(f"Warning: .env file not found at {env_path}. Using default values.")
    except Exception as e:
        print(f"Error loading .env file: {e}")

# Load environment variables
load_env_vars()

# Email settings from environment variables
EMAIL_HOST = get_required_env_var("EMAIL_HOST")
EMAIL_USER = get_required_env_var("EMAIL_USER")
EMAIL_PASSWORD = get_required_env_var("EMAIL_PASSWORD")

# Validate email format
def validate_email(email: str) -> bool:
    """Validate email format."""
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

if not validate_email(EMAIL_USER):
    raise ConfigError(f"Invalid email format for EMAIL_USER: {EMAIL_USER}")

# Get recipient emails from environment variable
def get_recipient_emails() -> list:
    """
    Get recipient emails from environment variable.
    Expects a comma-separated list of email addresses.

    Returns:
        list: List of validated email addresses

    Raises:
        ConfigError: If no valid email addresses are found
    """
    recipients_str = get_required_env_var("EMAIL_RECIPIENTS")
    recipients = [email.strip() for email in recipients_str.split(",")]

    # Validate each email
    invalid_emails = [email for email in recipients if not validate_email(email)]
    if invalid_emails:
        raise ConfigError(f"Invalid email format(s) in EMAIL_RECIPIENTS: {', '.join(invalid_emails)}")

    return recipients

# Initialize recipient list
EMAIL_RECIPIENTS = get_recipient_emails()

# API Keys
PERPLEXITY_API_KEY = get_required_env_var("PERPLEXITY_API_KEY")

# Output directory setup
OUTPUT_DIR = os.path.join(BASE_DIR, "latest_articles")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Directory for newsletter attachments
ATTACHMENTS_DIR = os.path.join(OUTPUT_DIR, "newsletter_attachments")
os.makedirs(ATTACHMENTS_DIR, exist_ok=True)

# Directory for CSS files
CSS_DIR = os.path.join(BASE_DIR, "css")
os.makedirs(CSS_DIR, exist_ok=True)

# Directory for caching API responses
CACHE_DIR = os.path.join(BASE_DIR, "cache")
os.makedirs(CACHE_DIR, exist_ok=True)

# Configure logging
logging.basicConfig(
    filename=os.path.join(OUTPUT_DIR, "newsletter_system.log"),
    level=logging.DEBUG, #changed from INFO to DEBUG
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Time thresholds
TIME_THRESHOLD = 24 * 3600  # 24 hours in seconds - for RSS and email collection
CLEANUP_THRESHOLD = 2  # Days - for email cleanup

# Deduplication settings
DEDUPLICATION_ENABLED = False  # Master switch to enable/disable deduplication logic everywhere
ENABLE_DEDUPLICATION = False  # Master switch for deduplication (legacy, for backward compatibility)
DEDUPLICATION_WINDOW_DAYS = 30  # How far back to check for duplicates
DEDUPLICATION_METHOD = "strict"  # Options: "strict" (exact match) or "fuzzy" (similar content)

# Main color scheme - centralized for easy theming
COLORS = {
    "primary": "#00827C",
    "primary_dark": "#00635F",
    "primary_light": "#BDD7D6",
    "secondary": "#3B8589",
    "background": "#e3f1ee",
    "background_light": "#F8F8FF",
    "background_alt": "#FFFFFF",
    "text_dark": "#333333",
    "text_medium": "#444444",
    "text_light": "#666666",
    "accent": "#5E9E9A",
    "youtube_red": "#FF0000",
    "youtube_light": "#FFE4E4",
    "dark_mode": {
        "background": "#1a1a1a",
        "background_alt": "#2a2a2a",
        "text_dark": "#f0f0f0",
        "text_medium": "#e0e0e0",
        "text_light": "#b0b0b0",
        "primary": "#00a39e",  # Slightly brighter for dark mode
        "primary_light": "#004d4a",
        "accent": "#4a8a86",
        "border": "#404040",
        "card_background": "#333333",
        "link": "#66b3b0",
        "link_hover": "#99c9c7"
    }
}

# Import keywords from separate file - using absolute path
keywords_path = os.path.join(BASE_DIR, 'keywords_config_v01.py')
sys.path.insert(0, BASE_DIR)  # Add the directory to Python path

try:
    from keywords_config import get_keywords
    KEYWORDS, NEGATIVE_KEYWORDS, YOUTUBE_KEYWORDS, YOUTUBE_NEGATIVE_KEYWORDS = get_keywords()
    logging.info(f"Successfully loaded keywords from {keywords_path}")
    print(f"Successfully loaded keywords from {keywords_path}")
except ImportError:
    logging.error(f"Failed to import keywords_config_v01.py. Check that it exists at {keywords_path}")
    print(f"ERROR: keywords_config_v01.py not found at {keywords_path}. Please create this file with your keywords.")
    print("See example_keywords_config.py for a template.")
    sys.exit(1)

# List of RSS feeds to fetch
RSS_FEEDS = [
    "https://imo-epublications.org/rss/content/all/most_recent_items?fmt=rss",
    "https://www.hu-berlin.de/de/pr/medien/nachrichten.rss",
    "https://v.hu-berlin.de/rss_de.xml",
    "https://info.orcid.org/feed/",
    "https://digital.soas.ac.uk/rss/all_rss.xml",
    "https://utorontopress.com/feed/",
    "https://wcd.copernicus.org/xml/rss2_0.xml",
    "https://www.livescience.com/feeds/all",
    "https://kluwerlawonline.com/feeds/AllJournals",
    "https://bsky.app/profile/did:plc:ngv3q2q4lusx6crjbwj46kcm/rss",
   # "https://www.generali.com/.rest/rss/v1/feed?name=pressReleases",
    "https://www.destatis.de/SiteGlobals/Functions/RSSFeed/DE/RSSNewsfeed/Aktuell.xml",
    "https://rss.sueddeutsche.de/alles",
    "https://think.ing.com/rss",
    "https://bsky.app/profile/did:plc:s7nqwivai73zfz54tsscbr2d/rss",
    "https://www.science.org/action/showFeed?type=etoc&feed=rss&jc=science",
    "https://www.ncei.noaa.gov/access/monitoring/monthly-report/rss.xml",
    "https://www.hec.edu/en/knowledge/feed.xml",
    "https://www.science.org/action/showFeed?type=etoc&feed=rss&jc=sciadv",
    "https://www.science.org/rss/news_current.xml",
    "https://www.hec.edu/en/news/feed.xml",
    "https://mid.ecb.europa.eu/rss/mid.xml",
    "https://presseportal.greenpeace.de/press_releases.atom",
    "https://www.bbva.com/es/rss/notas-de-prensa/",
    "https://www.kfw.de/%C3%9Cber-die-KfW/Service/KfW-Newsdienste/RSS-Feed/Pressemitteilungen-der-KfW-Bankengruppe.xml",
    "https://www.kfw.de/%C3%9Cber-die-KfW/Service/KfW-Newsdienste/RSS-Feed/Aktuelle-Meldungen-aus-der-KfW-Bankengruppe.xml",
    "https://www.kfw.de/%C3%9Cber-die-KfW/Service/KfW-Newsdienste/RSS-Feed/Aktuelle-Meldungen-aus-dem-Bereich-Research.xml",
    "https://feeds.megaphone.fm/GLD9218176758",
    "https://www.bis.org/doclist/mgmtspeeches.rss",
    "https://www.bis.org/doclist/cbspeeches.rss",
    "https://www.bis.org/doclist/reshub_papers.rss",
    "https://www.bis.org/doclist/bis_fsi_publs.rss",
    "https://www.morganstanley.com/press-releases.msfeed.xml",
    "https://jpmorganchaseco.gcs-web.com/rss/news-releases.xml",
    "https://www.ubs.com/global/en/investment-bank/insights-and-data/global-research/_jcr_content/mainpar/toplevelgrid_copy/col1/responsivepodcast.rss20.xml",
    "https://www.dbresearch.com/PROD/RPS_EN-PROD/RSS_GROUP_HOME_EN.calias",
    "https://api.substack.com/feed/podcast/2252/private/6578dc75-e126-4d54-83ca-34f1cc4902b8.rss",
    "https://climate.nasa.gov/news/rss.xml",
    "https://strathprints.strath.ac.uk/cgi/latest_tool?output=Atom",
    "https://collections.unu.edu/collection/UNU:1903?tpl=2",
    "https://www.undrr.org/rss.xml",
    "https://globalclimaterisks.org/news/feed/",
    "https://feeds.feedburner.com/GlobalPressRoom",
    "https://www.dnb.nl/en/rss/16451/6882",
    "https://www.federalreserve.gov/feeds/press_all.xml",
    "https://www.federalreserve.gov/feeds/currentfaqs.xml",
    "https://www.federalreserve.gov/feeds/working_papers.xml",
    "https://www.federalreserve.gov/feeds/feds.xml",
    "https://www.federalreserve.gov/feeds/ifdp.xml",
    "https://news.un.org/feed/subscribe/en/news/all/rss.xml",
    "https://news.un.org/feed/subscribe/en/news/region/europe/feed/rss.xml",
    "https://news.un.org/feed/subscribe/en/news/topic/human-rights/feed/rss.xml",
    "https://news.un.org/feed/subscribe/en/news/topic/climate-change/feed/rss.xml",
    "http://global.oup.com/academic/category/law/?view=RSS",
    "https://www.esrb.europa.eu/rss/press.xml",
    "https://www.esrb.europa.eu/rss/pub.rss",
    "https://www.esrb.europa.eu/rss/esrb_policy.rss",
    "https://www.esrb.europa.eu/rss/nat_policy.rss",
    "https://www.theguardian.com/europe/rss",
    "https://www.science.org/action/showFeed?type=axatoc&feed=rss&jc=science",
    "https://www.theguardian.com/uk/commentisfree",
    "https://www.theguardian.com/environment/climate-crisis/rss",
    "https://www.theguardian.com/world/rss",
    "https://www.theguardian.com/politics/rss",
    "https://www.theguardian.com/business/rss",
    "https://www.theguardian.com/science/rss",
    "https://www.theguardian.com/technology/rss",
    "https://www.theguardian.com/global-development/rss",
    "https://www.nature.com/nature.rss",
    "https://iopscience.iop.org/nsearch/rss?&searchDatePeriod=anytime&terms=climate%20change",
    "https://iopscience.iop.org/nsearch/rss?&searchDatePeriod=anytime&terms=%20ESG",
    "https://iopscience.iop.org/nsearch/rss?&searchDatePeriod=anytime&terms=climate%20risk",
    "https://iopscience.iop.org/nsearch/rss?&searchDatePeriod=anytime&terms=sustainable%20finance",
    "https://www.tagesschau.de/inland/index~rss2.xml",
    "https://www.tagesschau.de/ausland/index~rss2.xml",
    "https://www.tagesschau.de/wirtschaft/index~rss2.xml",
    "https://www.centralbank.ie/feeds/news-media-feed",
    "https://www.centralbank.ie/feeds/markets-updates-feed",
    "https://www.bankofgreece.gr/_layouts/15/BPC.RssFeeder/RssPage.aspx?Param=Publications&lang=en",
    "https://www.bankofgreece.gr/_layouts/15/BPC.RssFeeder/RssPage.aspx?Param=PressReleases&lang=en",
    "https://www.tagesschau.de/wissen/index~rss2.xml",
    "https://www.tagesschau.de/investigativ/index~rss2.xml",
    "https://www.faz.net/rss/aktuell/",
    "https://ec.europa.eu/newsroom/eba/feed?item_type_id=1642&lang=en&orderby=item_date",
    "https://www.presseportal.de/rss/politik.rss2",
    "https://www.presseportal.de/rss/finanzen.rss2",
    "https://www.presseportal.de/rss/banken.rss2",
    "https://www.bafin.de/DE/Service/TopNavigation/RSS/_function/rssnewsfeed.xml",
    "https://www.bafin.de/DE/Service/TopNavigation/RSS/_function/RSS_Massnahmen.xml",
    "https://www.bafin.de/DE/Service/TopNavigation/RSS/_function/rssnewsfeed.xml",
    "https://www.bafin.de/DE/Service/TopNavigation/RSS/_function/rssnewsfeed.xml",
    "https://direct.mit.edu/rss/site_1000041/LatestOpenIssueArticles_1000023.xml",
    "https://www.bafin.de/DE/Service/TopNavigation/RSS/_function/RSS_Aufsicht.xml",
    "https://www.bafin.de/DE/Service/TopNavigation/RSS/_function/RSS_Massnahmen.xml",
    "https://www.bafin.de/DE/Service/TopNavigation/RSS/_function/RSS_Angebotsausschreibung.xml",
    "https://www.europarl.europa.eu/rss/doc/press-releases/en.xml",
    "https://www.finanzen.net/rss/analysen",
    "https://www.europarl.europa.eu/rss/doc/top-stories/en.xml",
    "https://www.europarl.europa.eu/rss/doc/agendas-news/en.xml",
    "https://bsky.app/profile/did:plc:7d33vjrei7fz3tlxbrgdnt37/rss",
    "https://www.europarl.europa.eu/rss/doc/last-news-committees/en.xml",
    "https://www.europarl.europa.eu/rss/doc/plenary/en.xml",
    "https://direct.mit.edu/rss/site_1000097/1000051.xml",
    "https://www.europarl.europa.eu/rss/doc/last-news-committees/en.xml",
    "https://www.europarl.europa.eu/rss/doc/agendas-committees/en.xml",
    "https://direct.mit.edu/rss/site_1000065/LatestOpenIssueArticles_1000035.xml",
    "https://www.europarl.europa.eu/rss/doc/opinions/en.xml",
    "https://www.europarl.europa.eu/rss/doc/publications-committees/en.xml",
    "https://direct.mit.edu/rss/site_1000045/LatestOpenIssueArticles_1000025.xml",
    "https://www.europarl.europa.eu/rss/committee/econ/en.xml",
    "https://www.europarl.europa.eu/rss/doc/last-news-delegations/en.xml",
    "http://www.bankingsupervision.europa.eu/rss/press.html",
    "https://www.finanzen.net/rss/news",
    "https://www.bankingsupervision.europa.eu/rss/pub.html",
    "https://officialblogofunio.com/feed/",
    "http://eucenterillinois.blogspot.com/feeds/posts/default",
    "https://ecfr.eu/feed/",
    "https://www.euractiv.com/?feed=mcfeed",
    "https://rss.nytimes.com/services/xml/rss/nyt/Europe.xml",
    "https://rss.sueddeutsche.de/alles",
    "https://newsfeed.zeit.de/index",
    "https://www.handelsblatt.com/contentexport/feed/schlagzeilen",
    "https://www.handelsblatt.com/contentexport/feed/politik",
    "https://www.europeanlawblog.eu/rss.xml",
    "https://ecfr.eu/feed/",
    "https://rss.dw.com/rdf/rss-en-all",
    "https://officialblogofunio.com/feed/",
    "https://www.europarl.europa.eu/rss/doc/top-stories/de.xml",
    "https://www.europarl.europa.eu/rss/doc/agendas-news/de.xml",
    "https://www.europarl.europa.eu/rss/doc/newsletters/de.xml",
    "https://www.nature.com/nclimate.rss",
    "http://wupperinst.org/rss_news_en.php",
    "http://feeds.harvardbusiness.org/harvardbusiness/videoideacast",
    "https://www.ilo.org/de/rss.xml",
    "http://feeds.harvardbusiness.org/harvardbusiness/",
    "https://ssir.org/site/rss_2.0",
    "https://insights.som.yale.edu/rss",
    "https://www.pik-potsdam.de/de/aktuelles/nachrichten/nachrichten/rss.xml",
    "https://www.pik-potsdam.de/en/news/latest-news/latest-news/rss.xml",
    "https://www.ufz.de/index.php?de=34299&vera_rss",
    "https://www.ufz.de/index.php?de=18084&vera_rss",
    "https://www.semafor.com/rss.xml",
 #   "https://www.imf.org/en/rss-list/feed?category=FANDD_ENG",
 #   "https://www.imf.org/en/News/RSS?TemplateID={2FA3421A-F179-46B6-B8D9-5C65CB4A6584}",
#    "https://www.imf.org/en/news/rss?Language=ENG&Country=DEU",
#    "https://www.imf.org/en/rss-list/feed?category=WHATSNEW",
#    "https://www.imf.org/en/Publications/RSS?language=eng&series=World%20Economic%20Outlook",
#    "https://www.imf.org/en/Publications/RSS?language=eng&series=IMF%20Working%20Papers",
#
#     "https://www.imf.org/en/Publications/RSS?language=eng&series=Regional%20Economic%20Outlook",
    "https://www.leibniz-gemeinschaft.de/rss.xml",
    "http://feeds.harvardbusiness.org/harvardbusiness/videoideacast",
    "http://feeds.harvardbusiness.org/harvardbusiness?format=xml",
    "https://onlinelibrary.wiley.com/action/showFeed?jc=19447973&type=etoc&feed=rss",
    "https://ascelibrary.org/action/showFeed?type=etoc&feed=rss&jc=jwrmd5",
    "https://rss.sciencedirect.com/publication/science/13648152",
    "https://rss.sciencedirect.com/publication/science/03091708",
    "https://hydrol-earth-syst-sci.net/xml/rss2_0.xml",
    "https://onlinelibrary.wiley.com/rss/journal/10.1111/(ISSN)1752-1688",
    "https://rss.sciencedirect.com/publication/science/00221694",
    "https://iopscience.iop.org/1748-9326/?rss=1",
    "https://iopscience.iop.org/journal/rss/2752-5295",
    "http://http://feeds.rsc.org/rss/se",
    "http://feeds.rsc.org/rss/su",
    "http://feeds.rsc.org/rss/ea",
    "https://worldscientific.com/action/showFeed?ui=0&mi=gwdp8o&type=search&feed=rss&query=%2526AllField%253Dclimate%252Bchange%2526access%253D18%2526content%253DarticlesChapters%2526target%253Ddefault",
    "https://www.mitpressjournals.org/action/showFeed?ui=k928&mi=3il28u&ai=t9&jc=evco&type=etoc&feed=rss",
    "https://worldscientific.com/action/showFeed?ui=0&mi=gwdp8o&type=search&feed=rss&query=%2526AllField%253DESG%2526access%253D18%2526content%253DarticlesChapters%2526target%253Ddefault",
    "https://link.springer.com/search.rss?facet-content-type=Article&facet-journal-id=10898&channel-name=Journal+of+Global+Optimization",
    "https://worldscientific.com/action/showFeed?ui=0&mi=gwdp8o&type=search&feed=rss&query=%2526AllField%253Dclimate%252Brisk%2526access%253D18%2526content%253DarticlesChapters%2526target%253Ddefault",
    "https://www.journals.elsevier.com/computers-and-operations-research/rss",
    "https://feeds.nature.com/nclimate/rss/current?format=xml",
    "https://www.cambridge.org/elt/peterroach/roach-rss.xml",
    "https://www.mdpi.com/rss/journal/ijfs",
    "https://cepr.org/rss/vox-content",
    "https://cepr.org/rss/discussion-paper",
    "https://cepr.org/rss/news",
    "https://cepr.org/rss/events",
    "https://www.tandfonline.com/feed/rss/tsfi20",
    "https://www.tandfonline.com/feed/rss/rcli20",
    "https://www.tandfonline.com/feed/rss/oaes21",
    "https://www.tandfonline.com/feed/rss/oabm20",
    "https://www.tandfonline.com/feed/rss/ufaj20",
    "https://www.tandfonline.com/feed/rss/raec20",
    "https://www.tandfonline.com/feed/rss/rwin20",
    "https://www.tandfonline.com/feed/rss/tjem20",
    "https://www.tandfonline.com/feed/rss/tjds20",
    "https://www.tandfonline.com/feed/rss/tsue20",
    "https://www.tandfonline.com/feed/rss/tcpo20",
    "https://www.tandfonline.com/feed/rss/tcld20",
    "https://www.tandfonline.com/feed/rss/rero20",
    "https://www.tandfonline.com/feed/rss/rcls20",
    "https://www.tandfonline.com/feed/rss/raie20",
    "https://www.tandfonline.com/feed/rss/tjds20",
    "https://jpmorganchaseco.gcs-web.com/rss/news-releases.xml",
    "https://www.devex.com/news/feed.rss",
    "https://www.sfrg.org/blog-feed.xml",
    "https://sustainablefinancealliance.org/feed/",
   # "https://vitalbriefing.com/feed/",
    "http://sustainablefinanceblog.com/feed/",
    "https://www.forrester.com/blogs/category/sustainability/sustainable-finance/feed/",
    "https://www.bloomberg.com/professional/insights/category/sustainable-finance/feed/",
    "https://feeds.bloomberg.com/business/news.rss",
    "https://www.bundesbank.de/service/rss/en/633292/feed.rss",
    "https://www.bundesbank.de/service/rss/en/633306/feed.rss",
    "https://www.bundesbank.de/service/rss/en/633296/feed.rss",
    "https://www.bundesbank.de/service/rss/en/633312/feed.rss",
    "https://rss.arxiv.org/rss/q-fin.EC",
    "https://rss.arxiv.org/rss/econ",
    "https://rss.arxiv.org/rss/q-fin.RM",
    "https://rss.arxiv.org/rss/q-fin.EC",
    "https://rss.arxiv.org/rss/q-fin.PM",
    "https://rss.arxiv.org/rss/q-fin.ST",
    "https://rss.arxiv.org/rss/econ.GN",
    "http://www.iac.ethz.ch/news-and-events/news-en/_jcr_content.feed",
    "https://www.geomar.de/en/feed/climate",
    "http://www.oceanblogs.org/feed",
    "https://www.pbl.nl/en/rss-feeds",
    "https://feeds.feedburner.com/ConservationInternationalBlog",
    "https://www.earthdata.nasa.gov/learn/rss-feeds",
    "https://www.climate.gov/feeds/news-features/highlights.rss",
    "http://feeds.nature.com/nclimate/rss/current",
    "https://www.climatesolutions.org/rss/climatesolutions",
    "https://www.climatesolutions.org/rss/solutionsstories",
    "https://www.climatesolutions.org/rss/climatecast",
    "https://www.climatesolutions.org/rss/newenergycities",
    "http://feeds.nature.com/nclimate/rss/aop",
    "http://feeds.rsc.org/rss/ee",
    "http://feeds.rsc.org/rss/ya",
    "https://www.climatesolutions.org/rss/nwbiocarbon",
    "http://feeds.rsc.org/rss/va",
    "https://www.climate.gov/feeds/news-features/casestudies.rss",
    "http://feeds.rsc.org/rss/ea",
    "https://www.climatesolutions.org/rss/saf",
    "http://feeds.rsc.org/rss/em",
    "https://www.climatesolutions.org/rss/blcs",
    "http://feeds.rsc.org/rss/ew",
    "https://www.climate.gov/feeds/news-features/climateand.rss",
    "http://feeds.rsc.org/rss/se",
    "https://www.unep.org/news-and-stories/rss.xml",
    "https://www.sciencedaily.com/newsfeeds.html",
    "https://www.eurotopics.net/export/de/rss.xml",
    "https://www.esf.de/SiteGlobals/Functions/RSSFeed/DE/Aktuelles/Aktuelles.xml?nn=c610df2a-40bb-48bf-8b32-c629392a0115",
    "https://www.ble.de/SiteGlobals/Functions/RSS/DE/Startseite.xml?nn=633724",
    "https://ssir.org/site/rss_2.0",
    "https://bdi.eu/rss",
    "http://www.dguv.de/de/Index.xml.jsp",
    "https://www.gdv.de/service/rss/gdv/92670/feed.rss",
    "https://eur-lex.europa.eu/EN/display-feed.rss?rssId=162",
    "https://www.euractiv.com/?feed=mcfeed",
    "https://www.osce.org/rss/latest-stories",
    "https://www.hereon.de/communication_media/rss/rss_news_helmholtz.en.xml",
    "https://www.irena.org/iapi/rssfeed/News",
    "https://www.irena.org/iapi/rssfeed/Publications",
    "https://ssir.org/site/rss_2.0",
    "https://www.ifo.de/pressemitteilungen/rss.xml",
    "https://www.iwkoeln.de/rss/iw-komplett.xml",
    "https://www.climate.gov/feeds/news-features/decisionmakers.rss",
    "https://www.iwkoeln.de/rss/umwelt-und-energie.xml",
    "https://www.climate.gov/feeds/news-features/take5.rss",
    "https://www.iwkoeln.de/rss/iw-studien-1.xml",
    "https://www.climate.gov/feeds/news-features/climatetech.rss",
    "https://www.iwkoeln.de/rss/iw-kurzberichte-deutschsprachig.xml",
    "https://www.diw.de/de/rss_publications.xml",
    "https://www.climate.gov/feeds/news-features/beyond-the-data.rss",
    "https://www.diw.de/de/rss_podcast_wochenbericht.xml",
    "https://www.climate.gov/feeds/news-features/enso.rss",
    "https://www.diw.de/de/rss_podcast_fossilfrei.xml",
    "https://www.climate.gov/feeds/news-features/polar-vortex.rss",
    "https://www.diw.de/de/rss_roundup.xml",
    "https://www.climate.gov/feeds/news-features/understandingclimate.rss",
    "https://www.diw.de/de/rss_news.xml",
    "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/internacional/portada",
    "https://feeds.elpais.com/mrss-s/pages/ep/site/english.elpais.com/portada",
    "https://feeds.elpais.com/mrss-s/list/ep/site/elpais.com/section/economia/subsection/negocios",
    "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/economia/portada",
    "https://www.bmas.de/SiteGlobals/Functions/RSSFeed/DE/RSSNewsfeed/RSSNewsfeed.xml",
    "https://www.eba.europa.eu/news-press/news/rss.xml",
    "https://www.esrb.europa.eu/rss/press.xml",
    "https://daily.jstor.org/feed/",
    "https://www.esrb.europa.eu/rss/pub.rss",
    "https://jacobin.com/rss",
    "https://www.mckinsey.com/insights/rss",
    "https://www.esrb.europa.eu/rss/esrb_policy.rss",
    "https://www.esrb.europa.eu/rss/nat_policy.rss",
    "https://www.eba.europa.eu/news-press/news/rss.xml",
    "https://www.idw.de/idw/idw-aktuell/index.xml",
    "https://www.bmuv.de/meldungen.rss",
    "https://www.hoganlovells.com/rss/rss?id={97C19BD8-FC75-4EB5-9EC9-A287DA3C3CE8}",
    "https://www.freshfields.com/en/rss/news/",
    "https://www.bakermckenzie.com/en/rss-landing/expertise/banking-and-finance",
    "https://www.bakermckenzie.com/en/rss-landing/expertise/capital-markets",
    "https://www.bakermckenzie.com/en/rss-landing/insight/all-events",
    "https://www.bakermckenzie.com/en/rss-landing/newsroom/all-news",
    "https://www.bakermckenzie.com/en/rss-landing/industries/automotive",
    "https://journals.ametsoc.org/journalissuetocrss/journals/aies/aies-overview.xml",
    "https://journals.ametsoc.org/journalissuetocrss/journals/bams/bams-overview.xml",
    "https://journals.ametsoc.org/journalissuetocrss/journals/eint/eint-overview.xml",
    "https://journals.ametsoc.org/journalissuetocrss/journals/apme/apme-overview.xml",
    "https://journals.ametsoc.org/journalissuetocrss/journals/atot/atot-overview.xml",
    "https://journals.ametsoc.org/journalissuetocrss/journals/atsc/atsc-overview.xml",
    "https://journals.ametsoc.org/journalissuetocrss/journals/clim/clim-overview.xml",
    "https://journals.ametsoc.org/journalissuetocrss/journals/hydr/hydr-overview.xml",
    "https://journals.ametsoc.org/journalissuetocrss/journals/phoc/phoc-overview.xml",
    "https://journals.ametsoc.org/journalissuetocrss/journals/amsm/amsm-overview.xml",
    "https://journals.ametsoc.org/journalissuetocrss/journals/mwre/mwre-overview.xml",
    "https://journals.ametsoc.org/journalissuetocrss/journals/wefo/wefo-overview.xml",
    "https://journals.ametsoc.org/journalissuetocrss/journals/wcas/wcas-overview.xml",
   #"https://www.dfg.de/service/rss/de/323556/feed.rss",
   #"https://www.dfg.de/service/rss/en/324778/feed.rss",
    "https://www.esma.europa.eu/rss.xml",
    "https://iopscience.iop.org/journal/rss/1748-9326",
    "https://ec.europa.eu/newsroom/eiopa/feed?item_type_id=1737&lang=en&orderby=item_date",
    "https://www.bankingsupervision.europa.eu/rss/pub.html",
    "https://hudoc.echr.coe.int/app/transform/rss?library=echrengpress&query=contentsitename:ECHR%20AND%20doctype=PR&sort=kpdate%20Descending&start=0&length=20&rankingModelId=11111111-0000-0000-0000-000000000000",
    "https://www.copernicus.eu/news/rss",
    "https://hudoc.echr.coe.int/app/transform/rss?library=echreng&query=((((((((((((((((((((%20contentsitename:ECHR%20AND%20(NOT%20(doctype=PR%20OR%20doctype=HFCOMOLD%20OR%20doctype=HECOMOLD))%20AND%20((respondent=%22DEU%22))%20AND%20((documentcollectionid=%22GRANDCHAMBER%22)))%20XRANK(cb=14)%20doctypebranch:GRANDCHAMBER)%20XRANK(cb=13)%20doctypebranch:DECGRANDCHAMBER)%20XRANK(cb=12)%20doctypebranch:CHAMBER)%20XRANK(cb=11)%20doctypebranch:ADMISSIBILITY)%20XRANK(cb=10)%20doctypebranch:COMMITTEE)%20XRANK(cb=9)%20doctypebranch:ADMISSIBILITYCOM)%20XRANK(cb=8)%20doctypebranch:DECCOMMISSION)%20XRANK(cb=7)%20doctypebranch:COMMUNICATEDCASES)%20XRANK(cb=6)%20doctypebranch:CLIN)%20XRANK(cb=5)%20doctypebranch:ADVISORYOPINIONS)%20XRANK(cb=4)%20doctypebranch:REPORTS)%20XRANK(cb=3)%20doctypebranch:EXECUTION)%20XRANK(cb=2)%20doctypebranch:MERITS)%20XRANK(cb=1)%20doctypebranch:SCREENINGPANEL)%20XRANK(cb=4)%20importance:1)%20XRANK(cb=3)%20importance:2)%20XRANK(cb=2)%20importance:3)%20XRANK(cb=1)%20importance:4)%20XRANK(cb=2)%20languageisocode:ENG)%20XRANK(cb=1)%20languageisocode:FRE&sort=kpdate%20Descending&start=0&length=20&rankingModelId=4180000c-8692-45ca-ad63-74bc4163871b",
    "https://ec.europa.eu/eurostat/en/search?p_p_id=estatsearchportlet_WAR_estatsearchportlet&p_p_lifecycle=2&p_p_state=maximized&p_p_mode=view&p_p_resource_id=atom&_estatsearchportlet_WAR_estatsearchportlet_collection=CAT_EURNEW",
    "https://ec.europa.eu/eurostat/en/search?p_p_id=estatsearchportlet_WAR_estatsearchportlet&p_p_lifecycle=2&p_p_state=maximized&p_p_mode=view&p_p_resource_id=atom&_estatsearchportlet_WAR_estatsearchportlet_collection=dataset",
    "https://ec.europa.eu/eurostat/en/search?p_p_id=estatsearchportlet_WAR_estatsearchportlet&p_p_lifecycle=2&p_p_state=maximized&p_p_mode=view&p_p_resource_id=atom&_estatsearchportlet_WAR_estatsearchportlet_collection=CAT_PREREL",
    "https://dev.eiopa.europa.eu/RSS/S2_XBRL_RSS.xml",
    "https://eur-lex.europa.eu/DE/display-feed.rss?rssId=162",
    "https://www.eea.europa.eu/highlights/archive/RSS2",
    "https://www.eea.europa.eu/publications/latest/RSS2",
    "https://www.eea.europa.eu/data-and-maps/data/RSS2",
    "https://www.eea.europa.eu/data-and-maps/figures/RSS2",
    "https://wiiw.ac.at/rss.xml",
    "https://ecipe.org/feed/",
    "https://www.iaea.org/feeds/topnews",
    "https://www.iaea.org/feeds/dgstatements",
    "https://www.iaea.org/feeds/publications",
    "https://www.deutschlandfunk.de/nachrichten-100.rss",
    "https://www.deutschlandfunk.de/politikportal-100.rss",
    "https://www.deutschlandfunk.de/wirtschaft-106.rss",
    "https://www.deutschlandfunk.de/wissen-106.rss",
    "https://bsky.app/profile/did:plc:zlrkzqqu26xorrz3zfgwha2x/rss",
    "https://www.deutschlandfunk.de/kulturportal-100.rss",
    "https://www.deutschlandfunk.de/europa-112.rss",
    "https://www.deutschlandfunk.de/gesellschaft-106.rss",
    "https://www.deutschlandfunk.de/sportportal-100.rss",
    "https://financefwd.com/de/feed/",
    "https://rpc.cfainstitute.org/RPC-Publications-Feed",
    "https://www.unep.org/news-and-stories/rss.xml",
    "https://www.unepfi.org/category/publications/rss",
    "https://markcliffe.wordpress.com/feed/",
    "https://bdi.eu/rss",
    "https://www.dihk-verlag.de/feed.aspx?id=1",
    "http://feeds.harvardbusiness.org/harvardbusiness/",
    "https://news.harvard.edu/gazette/feed/",
    "https://executiveeducation.wharton.upenn.edu/thought-leadership/wharton-at-work/feed/",
    "https://financefwd.com/de/feed/",
    "https://www.ft.com/news-feed?format=rss",
    "https://feeds.elpais.com/mrss-s/pages/ep/site/cincodias.elpais.com/section/ultimas-noticias/portada",
    "https://www.straitstimes.com/news/business/rss.xml",
    "https://www.risk.net/feeds/rss/category/cutting-edge",
    "https://www.straitstimes.com/news/asia/rss.xml",
    "https://www.risk.net/feeds/rss/tag/asia",
    "https://www.straitstimes.com/news/world/rss.xml",
    "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
    "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml",
    "https://rss.nytimes.com/services/xml/rss/nyt/EnergyEnvironment.xml",
    "https://rss.nytimes.com/services/xml/rss/nyt/SmallBusiness.xml",
    "https://rss.nytimes.com/services/xml/rss/nyt/Economy.xml",
    "https://rss.nytimes.com/services/xml/rss/nyt/Dealbook.xml",
    "https://rss.nytimes.com/services/xml/rss/nyt/YourMoney.xml",
    "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml",
    "https://rss.nytimes.com/services/xml/rss/nyt/Climate.xml",
    "https://rss.nytimes.com/services/xml/rss/nyt/Science.xml",
    "https://rss.nytimes.com/services/xml/rss/nyt/RealEstate.xml",
    "https://rss.nytimes.com/services/xml/rss/nyt/MostViewed.xml",
    "https://www.nytimes.com/svc/collections/v1/publish/www.nytimes.com/column/ezra-klein/rss.xml",
    "https://restofworld.org/feed/latest",
    #"https://news.mit.edu/rss/feed",
    "https://news.mit.edu/rss/research",
    "https://news.mit.edu/rss/campus",
    "https://news.mit.edu/rss/topic/climate-change-and-sustainability",
    "https://news.mit.edu/rss/topic/earth-and-atmospheric-sciences",
    "https://www.europarl.europa.eu/rss/doc/top-stories/en.xml",
    "https://news.mit.edu/rss/topic/economics",
    "https://news.mit.edu/rss/topic/environment",
    "https://news.mit.edu/rss/topic/energy",
    "https://bsky.app/profile/did:plc:guefujpfgzbe6y3ix2bf62hr/rss",
    "https://bsky.app/profile/did:plc:jap4fkprwjzgvh43jlp62pmh/rss",
    "https://bsky.app/profile/did:plc:vdghr6occvjt6r4j5kgvgnxi/rss",
    "https://bsky.app/profile/did:plc:jjbb7kvn2rjcupiycuxoysia/rss",
    "https://bsky.app/profile/did:plc:icmgbi2h7mwmbojmifv7a7hp/rss",
    "https://bsky.app/profile/did:plc:s6434g77dgj5mr2cym345yr4/rss",
    "https://bsky.app/profile/did:plc:cfaooxkgfnxxgyynkjw25ufn/rss",
    "https://bsky.app/profile/did:plc:gwkoj3p542yn36gfesdyjqel/rss",
    "https://bsky.app/profile/did:plc:splem4tbrpi5hfm3w353tzqe/rss",
    "https://bsky.app/profile/did:plc:rqgety5gwmkzsrdpf6vjqhut/rss",
    "https://bsky.app/profile/did:plc:sbdge3lftdiekg6hycd4ibm4/rss",
    "https://bsky.app/profile/did:plc:2d6kuvaoa7qi6bq5cwq4isee/rss",
    "https://bsky.app/profile/did:plc:f63dvjj7ghivrx35h2iunj2y/rss",
    "https://bsky.app/profile/did:plc:2dwxs24526yfvmydneeu63ea/rss",
    "https://www.riksbank.se/en-gb/rss/press-releases/",
    "https://www.risk.net/feeds/rss/category/regulation/dodd-frank-act",
    "https://www.riksbank.se/en-gb/rss/speeches/",
    "https://www.norges-bank.no/en/rss-feeds/Articles-and-chronicles---Norges-Bank/",
    "https://www.norges-bank.no/en/rss-feeds/Occasional-Papers---Norges-Bank/",
    "https://www.nationalbanken.dk/api/rssfeed?topic=Analysis&lang=en",
    "https://www.risk.net/feeds/rss/category/regulation/mifid",
    "https://www.nationalbanken.dk/api/rssfeed?topic=Report&lang=en",
    "https://www.risk.net/feeds/rss/category/regulation/basel-committee",
    "https://www.nationalbanken.dk/api/rssfeed?topic=Working+Paper&lang=en",
    "https://www.risk.net/feeds/rss/category/journals",
    "https://www.nationalbanken.dk/api/rssfeed?topic=News&lang=en",
    "https://www.risk.net/feeds/rss/category/regulation/emir",
    "https://www.nationalbanken.dk/api/rssfeed?topic=Other+publications&lang=en",
    "https://bsky.app/profile/ec.europa.eu/rss",
    "https://bsky.app/profile/did:plc:6igyllqug5tvklzsh4mookla/rss",
    "https://bsky.app/profile/did:plc:bak7f4b3jsiqlpyo6o4ejaji/rss",
    "https://bsky.app/profile/did:plc:syrr7wxueqwc73abmd2gj7wq/rss",
    "https://bsky.app/profile/intbanker.bsky.social/rss",
    "https://bsky.app/profile/jakobthomae.bsky.social/rss",
    "https://bsky.app/profile/did:plc:zsn5w7bu7ywg3wfdvqczehzs/rss",
    "https://bsky.app/profile/did:plc:yc7qtx2guh22ieh3fmwe3yhj/rss",
    "https://bsky.app/profile/did:plc:wcnslwwko35gtmxftz2mflyx/rss",
    "https://bsky.app/profile/did:plc:h4lkczne5yqiwvd7mmqmpovu/rss",
    "https://www.businessdailyafrica.com/service/rss/bd/1939132/feed.rss",
    "https://www.srf.ch/news/bnf/rss/1646",
    "https://www.thehindu.com/business/feeder/default.rss",
    "https://www.risk.net/feeds/rss/category/regulation/solvency-ii",
    "https://www.thehindu.com/feeder/default.rss",
    "https://www.latimes.com/business/rss2.0.xml",
    "https://rss.asahi.com/rss/asahi/newsheadlines.rdf",
    "https://www.latimes.com/environment/rss2.0.xml",
    "https://www.latimes.com/world-nation/rss2.0.xml",
    "https://bsky.app/profile/did:plc:mee6vajyonx2kicob5zvhb4y/rss",
    "https://bsky.app/profile/did:plc:ov56vcbfhxxi6djpgiabwgkf/rss",
   # "https://www.washingtonpost.com/arcio/rss/category/opinions/",
    "https://feeds.washingtonpost.com/rss/world",
    "https://mainichi.jp/rss/etc/english_latest.rss",
    "http://feeds.washingtonpost.com/rss/business",
    "https://feeds.content.dowjones.io/public/rss/RSSWorldNews",
    "https://feeds.content.dowjones.io/public/rss/RSSMarketsMain",
    "https://en.yna.co.kr/RSS/news.xml",
    "https://feeds.content.dowjones.io/public/rss/socialeconomyfeed",
    "https://www.lanacion.com.co/feed/",
    "https://feeds.content.dowjones.io/public/rss/socialpoliticsfeed",
    "https://www.presseportal.de/rss/presseschau.rss2?langid=1",
    "https://gijn.org/feed/",
    "https://www.presseportal.de/rss/wirtschaft.rss2?langid=1",
    "https://www.nature.com/nature.rss",
    "https://www.wired.com/feed/category/business/latest/rss",
    "https://www.lanacion.com.co/feed/",
    "https://www.wired.com/feed/tag/ai/latest/rss",
    "https://www.presseportal.de/rss/umwelt.rss2?langid=1",
    "https://bsky.app/profile/did:plc:6okfkqs5whr275g4aahfnboz/rss",
    "https://www.presseportal.de/rss/finanzen.rss2?langid=1",
    "https://reporterbrasil.org.br/categorias/noticias/feed/",
    "https://www.presseportal.de/rss/bau-immobilien.rss2?langid=1",
    "https://www.wired.com/feed/category/science/latest/rss",
    "https://www.presseportal.ch/de/rss/presseportal.rss2?langid=1",
    "https://www.japantimes.co.jp/feed/",
    "https://bsky.app/profile/did:plc:lj6hjlpiksxjbmy2teo3ynoz/rss",
    "https://thecitypaperbogota.com/feed/",
    "https://www.spiegel.de/schlagzeilen/tops/index.rss",
    "https://theconversation.com/articles.atom?language=en",
    "https://www.spiegel.de/schlagzeilen/index.rss",
    "https://bsky.app/profile/did:plc:n3k7hkydcbm64tcvfcso3yt6/rss",
    "https://bsky.app/profile/bioversityciat.bsky.social/rss",
    "https://www.bankofengland.co.uk/rss/bank-overground",
    "https://www.project-syndicate.org/RSS",
    "https://www.bankofengland.co.uk/rss/events",
    "https://www.smh.com.au/rss/environment.xml",
    "https://www.bankofengland.co.uk/rss/knowledgebank",
    "https://www.smh.com.au/rss/feed.xml",
    "https://www.risk.net/feeds/rss/category/asset-management/insurance",
    "https://www.bankofengland.co.uk/rss/news",
    "https://www.risk.net/feeds/rss/category/risk-management/credit-risk",
    "https://www.bankofengland.co.uk/rss/publications",
    "https://www.risk.net/feeds/rss/category/risk-management/liquidity-risk",
    "https://www.bankofengland.co.uk/rss/speeches",
    "https://www.bde.es/wbe/en/inicio/rss/rss-noticias/",
    "https://www.bde.es/wbe/en/inicio/rss/rss-estudios-publicaciones/",
    "https://www.bde.es/wbe/en/inicio/rss/rss-normativa/",
    "https://bsky.app/profile/did:plc:v6otrz2gy7lej5cjbaqwbvgt/rss",
    "https://www.risk.net/feeds/rss/category/risk-management/operational-risk",
    "https://www.foreignaffairs.com/rss.xml",
    "https://www.risk.net/feeds/rss/category/risk-management/market-risk",
    "https://www.smh.com.au/rss/business.xml",
    "https://bsky.app/profile/did:plc:ppavi77mhpt7smqco4zeswop/rss",
    "https://www.bancaditalia.it/util/index.rss.html?lingua=en",
    "https://bsky.app/profile/did:plc:o3kyugmaw3xhfb5mwx365cvu/rss",
    "https://www.risk.net/feeds/rss/category/risk-management/asset-liability-management",
    "https://bsky.app/profile/did:plc:icmgbi2h7mwmbojmifv7a7hp/rss",
    "https://www.weareeurope.group/blog/blog-de-l-association-2/feed",
    "https://www.cisl.cam.ac.uk/news/feed/aggregator/RSS",
    "https://www.risk.net/feeds/rss/category/risk-management/settlement-risk",
    "https://fra.europa.eu/en/publications-and-resources/publications.rss.xml",
    "https://www.lemonde.fr/en/rss/une.xml",
    "https://www.risk.net/feeds/rss/category/asset-management/hedge-funds",
    "https://www.risk.net/feeds/rss/category/commodities/energy",
    "https://www.risk.net/feeds/rss/category/commodities/metals"



    # More feeds can be added here
]


# List of trusted newsletter senders
TRUSTED_SENDERS = [
    "contact@realclimate.org",
    "newsletter@circle-economy.com",
    "mailservice@oenb.at",
    "noreply@watson.ch",
    "newsletter@cicero.de",
    "mdebray@wmo.int",
    "noreply@die-dk.de",
    "webmestre@banque-france.fr",
    "info@drsc.de",
    "noreply@cleanenergywire.org",
    "system@ecoreporter-system.de",
    "whatsnew@yaleclimateconnections.org",
    "izaktuell@mc.iz.de",
    "office@regulatoryblog.eu",
    "accumulationzone@substack.com",
    "scienceadviser@aaas.sciencepubs.org",
    "sustainableviews@newsletter.ftspecialist.com",
    "sustainableviews@contact.ftspecialist.com",
    "treo@substack.com",
    "mailings@acumen.org",
    "newsletter@pfandbrief.de",
    "BaFinWebDE@newsletter.gsb.bund.de",
    "noreply@relai.lemonde.fr",
    "no-reply@notifications.corporatedisclosures.org",
    "noreply@springernature.com",
    "info@sciencebasedtargets.org",
    "BusinessAndFinance@newsletter.oecd.org",
    "hdhtvyklpsybbsvjouhiywvxngvdnapeuxg@simplelogin.co",
    "bafin@noreply.bund.de",
    "newsletter@gdv.de",
    "noreply@suomenpankki.eu",
    "noreply@suomenpankki.eu",
    "info@investmentofficer.com",
    "alert@corporatedisclosures.org",
    "mailservice@oenb.at",
    "foundationteam@economist.com",
    "publishing@email.mckinsey.com",
    "digital@euractiv.com",
    "info@investmentofficer.com",
    "info@esgnewsalerts.net",
    "bruegel@bruegel.org",
    "news@foreignaffairs.com",
    "newsletter@gdv.de",
    "support@iz.de",
    "info@esgnewsalerts.net",
    "news@foreignaffairs.com",
    "support@iz.de",
    "WorldBank@newsletterext.worldbank.org",
    "mediacentre@ebf.eu",
    "in.context.newsletter@jpmcib.jpmorgan.com",
    "newsletter@news.gsh.cib.natixis.com",
    "mediacentre@ebf.eu",
    "webmestre@banque-france.fr",
    "suomenpankki@info.eu",
    "noreply@esma.europa.eu",
    "english@boersen-zeitung.de",
    "newsletter@boersen-zeitung.de",
    "noreply@mail.bundesbank.de",
    "gazette@u.harvard.edu",
    "imo@onclusivenews.com",
    "noreply@esma.europa.eu",
    "maud.gauchon@edhec.edu",
    "newsletter@zia-deutschland.com",
    "talkingclimatenewsletter@substack.com",
    "information@kpmg.de",
    "information@kpmg.de",
    "scienceadviser@aaas.org",
    "webmestre@ngfs.net",
    "emailteam@emails.hbr.org",
    "versand@institut-fuer-menschenrechte.de",
    "accumulationzone@substack.com",
    "hello=ctvc.co@ghost.ctvc.co",
    "newsletter@forum-ng.org",
    "christopherchico@substack.com",
    "foundationteam@economist.com",
    "info@thebureauinvestigates.com",
    "no-reply@data.cdp.net",
    "oomi@energyinst.org",
    "mailservice@oenb.at",
    "noreply@talk.economistfoundation.org",
    "noreply@talk.economistfoundation.org",
    "info@oxfordmartin.ox.ac.uk",
    "gri@lse.ac.uk",
    "noreply@talk.economistfoundation.org",
    "office@regulatoryblog.eu",
    "newsletter@cicero.de",
    "energysnapshot@iea.org",
    "noreply@mail.bundesbank.de",
    "climatemajorityproject@substack.com",
    "publishing@email.mckinsey.com",
    "newsletters@bruegel.org",
    "bradzarnett@substack.com",
    "info@greencentralbanking.com",
    "esgonasunday@substack.com",
    "information@kpmg.de",
    "webmestre@ngfs.net",
    "comms@ceps.eu",
    "max.polwin@posteo.de",
    "newsletters@bruegel.org",
    "briefing@nature.com",
    "info@messagent.fdmediagroep.nl",
    "noreply@esma.europa.eu",
    "noreply@e.economist.com",
    "precourt_institute@stanford.edu",
    "WorldBank@newsletterext.worldbank.org",
    "newsletters@e.economist.com",
    "naturalcapitalproject@stanford.edu",
    "newsletters@nautil.us",
    "briefings@gs.com",
    "noreply@esma.europa.eu",
    "newsletters@e.economist.com",
    "acanizares-imf.org@shared1.ccsend.com",
    "Newsletter.Research@info.kfw.com",
    "info@greencentralbanking.com",
    "in.context.newsletter@jpmcib.jpmorgan.com",
    "newsletter@project-syndicate.org",
    "briefings@gs.com",
    "newsletter@netzpolitik.org",
    "info@climatepolicyinitiative.org",
    "in.context.newsletter@jpmcib.jpmorgan.com",
    "taylorandfrancis@email.taylorandfrancis.com",
    "instituteforprogress@substack.com",
    "info@messagent.fdmediagroep.nl",
    "contact@ksapa.org",
    "info@drawdown.org",
    "cvjuyelaghjjlajdfjvk@simplelogin.co",
    "noreply@esma.europa.eu",
    "info@messagent.fdmediagroep.nl",
    "instituteforprogress@substack.com",
    "yydoeixnyqdlazdeycvxxirbrfkgtguzyqduyryxgvtqggh@simplelogin.co",
    "maizieres.louise@newsletter.dihk.de",
    "gvqymqcsargigvwxlrabedhlfxkgvkz@simplelogin.co",
    "NewsDIHKBruessel@newsletter.dihk.de",
    "yydoeixnyqdlazdeycvxxirbrfkgtguzyqduyryxgvtqggh@simplelogin.co",
    "no-reply@substack.com",
    "noreply@omfif.org",
    "message@message.yale.edu",
    "noreply@waterbear.com",
    "WorldBank@newsletterext.worldbank.org",
    "hansstegeman@substack.com",
    "adamtooze@substack.com",
    "briefing@nature.com",
    "newsroom@eiopa.europa.eu",
    "no-reply@eba.europa.eu",
    "noreply@omfif.org",
    "gvqymqcsargigvwxlrabedhlfxkgvkz@simplelogin.co",
    "info@esgtoday.com",
    "WorldBank@newsletterext.worldbank.org",
    "axelle.vanwynsberghe@finance-watch.org",
    "no-reply@abos.bmas.de",
    "bruegel@bruegel.org",
    "noreply@esma.europa.eu",
    "noreply@omfif.org",
    "comms@ceps.eu",
    "info@vfu.de",
    "noreply-okta@bcg.com",
    "bcgcontactus@bcg.com",
    "reply-fe8c16707263007a7d-119_HTML-279977026-7291843-16226@e.economist.com",
    "pnasmail@nas.edu",
    "info@drsc.de",
    "briefings@gs.com",
    "noreply@omfif.org",
    "digital@project-syndicate.org",
    "newsletter@finanz-szene.de",
    "noreply@mail.bundesbank.de",
    "carbonrisk@substack.com",
    "comms@ceps.eu",
    "digital@euractiv.com",
    "emailteam@emails.hbr.org",
    "noreply@omfif.org",
    "leserservice@boersen-zeitung.de",
    "billmckibben@substack.com",
    "alexsteffen@substack.com",
    "talkingclimatenewsletter@substack.com",
    "accumulationzone@substack.com",
    "digital@euractiv.com",
    "emailteam@emails.hbr.org",
    "noreply@omfif.org",
    "newsletter@finanz-szene.de",
    "Quanta@SimonsFoundation.org",
    "news@news.dandc.eu",
    "nnxxwnwlcxrjhwubtpmvkuiryd@simplelogin.co",
    "briefing@nature.com",
    "pmjukysgdjyqbkbglwkktx@simplelogin.co",
    "editors@heatmap.news",
    "whitestaginvesting@substack.com",
    "sustainableviews@newsletter.ftspecialist.com",
    "sustainableviews@contact.ftspecialist.com",
    "treo@substack.com",
    "noreply@relai.lemonde.fr"

    #add more as you subscribe to more newsletters
]


class CircuitBreaker:
    def __init__(self, failure_threshold=5, reset_timeout=300):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.last_failure_time = None
        self.is_open = False

class RetryQueue:
    def __init__(self):
        self.queue = []
        self.processing = False
        self.retry_interval = 300  # 5 minutes
