"""Minimal PubMed/PMC helpers used by the Cochrane RIS reference resolver."""

from __future__ import annotations

import time
import xml.etree.ElementTree as ET
from typing import Any

import requests


NCBI_EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
USER_AGENT = "llm-evidence-retrieval-bias/standalone"


def _request(endpoint: str, params: dict[str, Any]) -> requests.Response:
    response = requests.get(
        f"{NCBI_EUTILS}/{endpoint}",
        params={"tool": "llm-evidence-retrieval-bias", **params},
        headers={"User-Agent": USER_AGENT},
        timeout=30,
    )
    response.raise_for_status()
    return response


def pubmed_esearch(query: str, retmax: int = 20) -> list[str]:
    response = _request(
        "esearch.fcgi",
        {
            "db": "pubmed",
            "term": query,
            "retmode": "json",
            "retmax": str(retmax),
        },
    )
    payload = response.json()
    return [str(pmid) for pmid in payload.get("esearchresult", {}).get("idlist", [])]


def pubmed_efetch_details(pmids: list[str]) -> list[dict[str, Any]]:
    if not pmids:
        return []
    response = _request(
        "efetch.fcgi",
        {
            "db": "pubmed",
            "id": ",".join(pmids),
            "retmode": "xml",
        },
    )
    root = ET.fromstring(response.text)
    return [_article_details(article) for article in root.findall(".//PubmedArticle")]


def pmids_to_pmc_info(pmids: list[str]) -> dict[str, dict[str, str]]:
    if not pmids:
        return {}
    response = _request(
        "elink.fcgi",
        {
            "dbfrom": "pubmed",
            "db": "pmc",
            "id": ",".join(pmids),
            "retmode": "xml",
        },
    )
    root = ET.fromstring(response.text)
    out: dict[str, dict[str, str]] = {}
    for link_set in root.findall(".//LinkSet"):
        pmid = _text(link_set.find("./IdList/Id"))
        pmcid = ""
        for link in link_set.findall("./LinkSetDb/Link/Id"):
            value = _text(link)
            if value:
                pmcid = f"PMC{value}"
                break
        if pmid:
            out[pmid] = {"pmcid": pmcid}
    for pmid in pmids:
        out.setdefault(str(pmid), {})
    time.sleep(0.34)
    return out


def _article_details(article: ET.Element) -> dict[str, Any]:
    medline = article.find("./MedlineCitation")
    article_node = medline.find("./Article") if medline is not None else None
    journal = article_node.find("./Journal") if article_node is not None else None
    journal_issue = journal.find("./JournalIssue") if journal is not None else None
    pub_date = journal_issue.find("./PubDate") if journal_issue is not None else None
    article_ids = article.findall("./PubmedData/ArticleIdList/ArticleId")
    return {
        "pmid": _text(medline.find("./PMID") if medline is not None else None),
        "title": _text(article_node.find("./ArticleTitle") if article_node is not None else None),
        "journal": _text(journal.find("./Title") if journal is not None else None),
        "year": _year(pub_date),
        "doi": _doi(article_ids),
        "authors": _authors(article_node),
        "publication_types": [
            _text(node)
            for node in article_node.findall("./PublicationTypeList/PublicationType")
        ]
        if article_node is not None
        else [],
    }


def _text(node: ET.Element | None) -> str:
    return "".join(node.itertext()).strip() if node is not None else ""


def _year(pub_date: ET.Element | None) -> str:
    if pub_date is None:
        return ""
    year = _text(pub_date.find("./Year"))
    if year:
        return year
    medline_date = _text(pub_date.find("./MedlineDate"))
    return medline_date[:4] if medline_date[:4].isdigit() else ""


def _doi(article_ids: list[ET.Element]) -> str:
    for article_id in article_ids:
        if article_id.attrib.get("IdType") == "doi":
            return _text(article_id)
    return ""


def _authors(article_node: ET.Element | None) -> list[str]:
    if article_node is None:
        return []
    authors = []
    for author in article_node.findall("./AuthorList/Author"):
        last = _text(author.find("./LastName"))
        initials = _text(author.find("./Initials"))
        collective = _text(author.find("./CollectiveName"))
        if last:
            authors.append(f"{last}, {initials}".strip().rstrip(","))
        elif collective:
            authors.append(collective)
    return authors
