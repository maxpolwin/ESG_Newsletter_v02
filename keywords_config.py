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
    "Green Asset Ratio", "European Sustainability Reporting Standards", "ESRS",
    "CSR Directive Implementation Act", " CSR-RUG ", "Deutscher Nachhaltigkeitskodex",
    " DNK ", "European Green Deal", "Paris Agreement", "Climate Risk", " CBAM ",
    "EU Carbon Border Adjustment Mechanism", "EU ETS", "European Union Emissions Trading System",
    "GHG Protocol", "Treibhausgas", "GHG", "Green House Gase", "EU Green Bonds Standard",
    "EU GBS", "EU Climate Transition Benchmark", "EU CTB", "Paris-Aligned",
    "EU PAB", "PCAF", "SDGs", "Supply Chain Sourcing Obligations Act", "LkSG",
    "Lieferkettensorgfaltspflichtengesetz", "B Corp", "Social Business", "Social Enterprise",
    "Basel IV", "Basel III", "Basel regulation", "MaRisk", "Stress Test", "IPCC", " COP ", "EOIPA",
    "EU Regulation on Deforestation-free Products", "net zero", "net-zero", "decarbonize", "decarbonise",
    "carbon credit", "biodiversity", "TNFD", "renaturation", "rewilding", "Nature based", "Nature Risk", "Biodiversity Risk" ," NbS ",
    "Nature-based", "Partnership for Carbon Accounting Financials", "Hydrogen", "Wasserstoff", "Decarbonising",
    "Decarbonizing", " NGFS ", "climate scenario", "climate policy", "stranded asset", "transition risk", "physical risk",
    "transition path", " VSME ", "(VSME)", "ESG-Score", "ESG-Rating", " CDR ", " CRCF ", "(CRCF)", "Carbon Removal", "Carbon Farming",
    "Swiss Climate Law", "CO2 Act", "CO2-Act", "HR DD", "HR Due Diligence", "ESG Rating", " ISSB ",
    "Implied Temperature Rise as a Measure of Alignment", "ITR-Score", "ITR-Rating", "Implied Temperature Rise", "Natural Capital"
}

    # Negative keywords - content containing these will be EXCLUDED
    negative_keywords = {
    "BaFin warnt vor", "Application deadline", " gene ", "hyrodgen bomb", "Marisken", "trabalho", "Sustentabilidade",
    "Mariskal", "Conspiracy", "Paluten", "CRAFT ATTACK", "Sustainy ",
    "TTPP", "blyaaaaaaaaaaaaaaaaat"
    
}

    return keywords, negative_keywords