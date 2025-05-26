#!/usr/bin/env python3
"""
Keywords Configuration for Newsletter System

This file defines the keywords used for filtering content from RSS feeds and email newsletters.
- Regular keywords are used to INCLUDE content that contains these terms
- Negative keywords are used to EXCLUDE content that contains these terms

Keyword matching rules:
- Keywords with spaces at the beginning or end will use exact word boundary matching
- Keywords without surrounding spaces will match even as parts of other words
"""

def get_keywords():
    """Return two lists of keywords: regular (include) and negative (exclude)."""

    # Regular keywords - content containing these will be INCLUDED
    keywords = {
    "EU Taxonomy", "EU-Taxonomy", "EU Taxonomy", "EU-Taxonomie", " CSRD ", " SFRD ", " NFRD ", "Sustainable Finance",
    " ESG ", "Sustainable Investment", "Omnibus", "CSDDD", "Corporate Sustainability Due Diligence Directive",
    " DNSH ", "Do No Significant Harm", "Principal Adverse Impact", " PAIs ", "(GAR)",
    "Green Asset Ratio", "European Sustainability Reporting Standards", "ESRS", "Sustainable Finance Disclosure",
    "CSR Directive Implementation Act", " CSR-RUG ", "Deutscher Nachhaltigkeitskodex",
    " DNK ", "European Green Deal", "Paris Agreement", "Climate Risk", " CBAM ",
    "EU Carbon Border Adjustment Mechanism", "EU ETS", "European Union Emissions Trading System",
    "GHG Protocol", "Treibhausgas", "Green House Gase", "EU Green Bonds Standard", "planetary boundaries",
    "EU GBS", "EU Climate Transition Benchmark", "EU CTB", "Paris-Aligned", "Klimafolgenforschung",
    "EU PAB", "PCAF", "SDGs", "Supply Chain Sourcing Obligations Act", "LkSG", "Attribution Science",
    "Lieferkettensorgfaltspflichtengesetz", "B Corp", "Social Business", "Social Enterprise", "Attributionsforschung",
    "Basel IV", "Basel III", "Basel regulation", "MaRisk", "Stress Test", "IPCC", "COP 30","EOIPA",
    "EU Regulation on Deforestation-free Products", "net zero", "net-zero", "decarbonize", "decarbonise",
    "carbon credit", "biodiversity", "TNFD", "renaturation", "rewilding", "Nature based", "Nature Risk", "Biodiversity Risk" ," NbS ",
    "Nature-based", "Partnership for Carbon Accounting Financials", "Hydrogen", "Wasserstoff", "Decarbonising",
    "Decarbonizing", " NGFS ", "climate scenario", "climate policy", "stranded asset", "transition risk", "physical risk",
    "transition path", " VSME ", "(VSME)", "ESG-Score", "ESG-Rating", " CDR ", " CRCF ", "(CRCF)", "Carbon Removal", "Carbon Farming",
    "Swiss Climate Law", "CO2 Act", "CO2-Act", "HR DD", "HR Due Diligence", "ESG Rating", " ISSB ",
    "Implied Temperature Rise as a Measure of Alignment", "ITR-Score", "ITR-Rating", "Implied Temperature Rise", "Natural Capital",
    "Grüner Pfandbrief", "ESG-Szenarioanalyse", "Join Impact Management", "Environmentally Extended Input-Output", "Sovereign Emissions Intensity", "follow the money method"
}

    # Negative keywords - content containing these will be EXCLUDED
    negative_keywords = {
    "BaFin warnt vor", "Application deadline", " gene ", "hyrodgen bomb", "Marisken", "trabalho", "Sustentabilidade",
    "Mariskal", "Conspiracy", "Paluten", "CRAFT ATTACK", "Sustainy ", "hydrogen bomb",
    "TTPP", "blyaaaaaaaaaaaaaaaaat", "detox", "Basti GHG", "Detox", "Blondie", "MM36"
}

    # YouTube-specific keywords - content containing these will be INCLUDED
    youtube_keywords_positive = {
        "ESG investing", "sustainable finance", "climate risk", "EU taxonomy", "CSRD",
        "climate scenario", "green bonds", "climate scenario analysis", "climate change finance",
        "sustainable investing", "ESG analysis", "climate transition", "decarboniz", 
        "sustainable banking", "green finance", "climate policy", "ESG reporting",
        "ESG strategy", "sustainable economy", "Omnibus package", "CSDDD",
        "climate finance", "ESG metrics", "climate stress test", "climate transition plan",
        "ESG disclosure", "climate adaptation", "ESG integration"
    }

    # YouTube-specific negative keywords - content containing these will be EXCLUDED
    youtube_keywords_negative = {
        "conspiracy", "fake news", "climate hoax", "ESG scam", "sustainable scam",
        "climate denial", "ESG fraud", "sustainable fraud", "climate conspiracy",
        "ESG conspiracy", "sustainable conspiracy", "climate scam", "ESG hoax", "AI-Driven",
        "sustainable hoax", "climate fraud", "ESG denial", "sustainable denial", "fun fact"
    }

    return keywords, negative_keywords, youtube_keywords_positive, youtube_keywords_negative