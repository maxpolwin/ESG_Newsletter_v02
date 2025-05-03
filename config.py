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

# Configure logging
logging.basicConfig(
    filename=os.path.join(OUTPUT_DIR, "newsletter_system.log"),
    level=logging.DEBUG, #changed from INFO to DEBUG
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Time thresholds
TIME_THRESHOLD = 24 * 3600  # 24 hours in seconds - for RSS and email collection
CLEANUP_THRESHOLD = 2  # Days - for email cleanup

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
}

# Import keywords from separate file - using absolute path
keywords_path = os.path.join(BASE_DIR, 'keywords_config_v01.py')
sys.path.insert(0, BASE_DIR)  # Add the directory to Python path

try:
    from keywords_config import get_keywords
    KEYWORDS, NEGATIVE_KEYWORDS = get_keywords()
    logging.info(f"Successfully loaded keywords from {keywords_path}")
    print(f"Successfully loaded keywords from {keywords_path}")
except ImportError:
    logging.error(f"Failed to import keywords_config_v01.py. Check that it exists at {keywords_path}")
    print(f"ERROR: keywords_config_v01.py not found at {keywords_path}. Please create this file with your keywords.")
    print("See example_keywords_config.py for a template.")
    sys.exit(1)

# List of RSS feeds to fetch
RSS_FEEDS = [
    "http://global.oup.com/academic/category/law/?view=RSS",
    "https://www.esrb.europa.eu/rss/press.xml",
    "https://www.esrb.europa.eu/rss/pub.rss",
    "https://www.esrb.europa.eu/rss/esrb_policy.rss",
    "https://www.esrb.europa.eu/rss/nat_policy.rss",
    "http://global.oup.com/academic/category/science-and-mathematics/earth-sciences-and-geography/?view=RSS",
    "http://global.oup.com/academic/category/science-and-mathematics/environmental-science/?view=RSS",
    "http://global.oup.com/academic/category/social-sciences/?view=RSS",
    "http://global.oup.com/academic/category/arts-and-humanities/?view=RSS",
    "https://www.theguardian.com/europe/rss",
    "https://www.theguardian.com/uk/commentisfree",
    "https://www.theguardian.com/environment/climate-crisis/rss",
    "https://www.theguardian.com/world/rss",
    "https://www.theguardian.com/politics/rss",
    "https://www.theguardian.com/business/rss",
    "https://www.theguardian.com/science/rss",
    "https://www.theguardian.com/technology/rss",
    "https://www.theguardian.com/global-development/rss",
    "https://www.tagesschau.de/inland/index~rss2.xml",
    "https://www.tagesschau.de/ausland/index~rss2.xml",
    "https://www.tagesschau.de/wirtschaft/index~rss2.xml",
    "https://www.tagesschau.de/wissen/index~rss2.xml",
    "https://www.tagesschau.de/investigativ/index~rss2.xml",
    "https://www.faz.net/rss/aktuell/",
    "https://ec.europa.eu/newsroom/eba/feed?item_type_id=1642&lang=en&orderby=item_date",
    "https://www.presseportal.de/rss/politik.rss2",
    "https://www.presseportal.de/rss/finanzen.rss2",
    "https://www.presseportal.de/rss/banken.rss2",
    "https://www.bafin.de/DE/Service/TopNavigation/RSS/_function/rssnewsfeed.xml",
    "https://www.europarl.europa.eu/rss/doc/press-releases/en.xml",
    "https://www.europarl.europa.eu/rss/doc/last-news-committees/en.xml",
    "http://www.bankingsupervision.europa.eu/rss/press.html",
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
    "http://www.feedly.com/home#subscription/feed/http://www.bruegel.org/rss?type=all",
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
    "https://www.ufz.de/index.php?de=34299&vera_rss",
    "https://www.ufz.de/index.php?de=18084&vera_rss",
    "https://www.semafor.com/rss.xml",
    "https://www.imf.org/en/rss-list/feed?category=FANDD_ENG",
    "https://www.imf.org/en/News/RSS?TemplateID={2FA3421A-F179-46B6-B8D9-5C65CB4A6584}",
    "https://www.imf.org/en/news/rss?Language=ENG&Country=DEU",
    "https://www.imf.org/en/rss-list/feed?category=WHATSNEW",
    "https://www.imf.org/en/Publications/RSS?language=eng&series=World%20Economic%20Outlook",
    "https://www.imf.org/en/Publications/RSS?language=eng&series=IMF%20Working%20Papers",
    "https://www.imf.org/en/Publications/RSS?language=eng&series=Regional%20Economic%20Outlook",
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
    "https://ksapa.org/category/sustainable-finance-esg/",
    "https://vitalbriefing.com/feed/",
    "http://sustainablefinanceblog.com/feed/",
    "https://www.forrester.com/blogs/category/sustainability/sustainable-finance/feed/",
    "https://www.bloomberg.com/professional/insights/category/sustainable-finance/feed/",
    "https://feeds.bloomberg.com/business/news.rss",
    "https://www.bundesbank.de/service/rss/en/633292/feed.rss",
    "https://www.bundesbank.de/service/rss/en/633306/feed.rss",
    "https://www.bundesbank.de/service/rss/en/633296/feed.rss",
    "https://www.bundesbank.de/service/rss/en/633312/feed.rss",
    "https://global.oup.com/academic/connect/rss/",
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
    "https://www.conservation.org/blog/rss-feeds",
    "https://www.climatesolutions.org/climate-solutions-rss-feeds",
    "https://www.earthdata.nasa.gov/learn/rss-feeds",
    "https://www.climate.gov/feeds",
    "http://feeds.nature.com/nclimate/rss/current",
    "http://feeds.nature.com/nclimate/rss/aop",
    "http://ec.europa.eu/environment/integration/research/newsalert/latest_alerts.htm",
    "http://feeds.rsc.org/rss/ee",
    "http://feeds.rsc.org/rss/ya",
    "http://feeds.rsc.org/rss/va",
    "http://feeds.rsc.org/rss/ea",
    "http://feeds.rsc.org/rss/em",
    "http://feeds.rsc.org/rss/ew",
    "http://feeds.rsc.org/rss/se",
    "https://www.unep.org/news-and-stories/rss.xml",
    "https://www.sciencedaily.com/newsfeeds.htm",
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
    "https://www.iwkoeln.de/rss/umwelt-und-energie.xml",
    "https://www.iwkoeln.de/rss/iw-studien-1.xml",
    "https://www.iwkoeln.de/rss/iw-kurzberichte-deutschsprachig.xml",
    "https://www.diw.de/de/rss_publications.xml",
    "https://www.diw.de/de/rss_podcast_wochenbericht.xml",
    "https://www.diw.de/de/rss_podcast_fossilfrei.xml",
    "https://www.diw.de/de/rss_roundup.xml",
    "https://www.diw.de/de/rss_news.xml",
    "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/internacional/portada",
    "https://feeds.elpais.com/mrss-s/pages/ep/site/english.elpais.com/portada",
    "https://feeds.elpais.com/mrss-s/list/ep/site/elpais.com/section/economia/subsection/negocios",
    "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/economia/portada",
    "https://www.bmas.de/SiteGlobals/Functions/RSSFeed/DE/RSSNewsfeed/RSSNewsfeed.xml",
    "https://www.eba.europa.eu/news-press/news/rss.xml",
    "https://www.esrb.europa.eu/rss/press.xml",
    "https://www.esrb.europa.eu/rss/pub.rss",
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
    "https://www.dfg.de/service/rss/de/323556/feed.rss",
    "https://www.dfg.de/service/rss/en/324778/feed.rss",
    "https://www.esma.europa.eu/rss.xml",
    "https://ec.europa.eu/newsroom/eiopa/feed?item_type_id=1736&lang=en&orderby=item_date",
    "https://ec.europa.eu/newsroom/eiopa/feed?item_type_id=1737&lang=en&orderby=item_date",
    "https://www.bankingsupervision.europa.eu/rss/pub.html",
    "http://www.echr.coe.int/Pages/home.aspx?p=ECHRRSSfeeds&c=",
    "https://www.copernicus.eu/news/rss",
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
    "https://www.ifo.de/en/pressemitteilungen/rss.xml",
    "https://www.diw.de/de/rss_news.xml",
    "https://www.diw.de/de/rss_roundup.xml",
    "https://www.diw.de/de/rss_publications.xml",
    "https://www.diw.de/de/rss_soep_news.xml"
    # More feeds can be added here
]


# List of trusted newsletter senders
TRUSTED_SENDERS = [
    "noreply@esma.europa.eu",
    "newsletters@bruegel.org",
    "bradzarnett@substack.com",
    "info@greencentralbanking.com",
    "esgonasunday@substack.com",
    "information@kpmg.de",
    "webmestre@ngfs.net",
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
    "noreply@omfif.org"

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
