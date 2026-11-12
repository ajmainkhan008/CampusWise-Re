"""
Google Gemini Extraction Service for CampusWise Internship Management.
Extracts structured internship announcements from CDC email notices.
"""

import os
import json
import re
import hashlib
import logging
from typing import Dict, Any, Tuple, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


def compute_content_hash(text: str) -> str:
    """
    Computes a deterministic SHA-256 hash of normalized text for duplicate detection (FR-38).
    """
    normalized = " ".join(text.strip().lower().split())
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()


def sanitize_input_text(text: str) -> str:
    """
    Sanitizes raw text to prevent XSS and malicious script injection (Requirement 11).
    """
    if not text:
        return ""
    # Strip dangerous HTML script tags
    sanitized = re.sub(r'<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>', '', text, flags=re.IGNORECASE)
    # Strip onload/onerror and other javascript inline handlers (quoted or unquoted)
    sanitized = re.sub(r'on\w+\s*=\s*(?:"[^"]*"|\'[^\']*\'|[^\s>]+)', '', sanitized, flags=re.IGNORECASE)
    # Strip javascript: URIs
    sanitized = re.sub(r'javascript:[^\s"\'<>]+', '', sanitized, flags=re.IGNORECASE)
    return sanitized.strip()


def heuristic_fallback_extractor(subject: str, content: str, source_link: str = "") -> Dict[str, Any]:
    """
    Fallback parser when Gemini API key is missing or offline.
    Extracts emails, URLs, dates, and subject hints without fabricating information.
    """
    # Extract URLs
    url_pattern = r'https?://[^\s<>"]+|www\.[^\s<>"]+'
    urls = re.findall(url_pattern, content)
    application_url = source_link or (urls[0] if urls else "")

    # Extract email addresses
    email_pattern = r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'
    emails = re.findall(email_pattern, content)
    application_email = emails[0] if emails else ""

    # Look for deadline hints (e.g., 2026-12-31, 30 October 2026, 1 November 2026, 30th Oct 2026, etc.)
    deadline_val = None
    deadline_match = re.search(
        r'(?:deadline|last date(?: of application| to apply)?|apply before|due date|apply by)(?:[\s:]+(?:is)?[\s:]*)([0-9]{1,4}[-/][0-9]{1,2}[-/][0-9]{1,4}|[A-Za-z]+ \d{1,2}(?:st|nd|rd|th)?,? \d{4}|\d{1,2}(?:st|nd|rd|th)? [A-Za-z]+,? \d{4})',
        content,
        re.IGNORECASE
    )
    if deadline_match:
        raw_date_str = deadline_match.group(1)
        # Strip ordinal suffixes (1st, 2nd, 3rd, 30th) and commas
        clean_date_str = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', raw_date_str, flags=re.IGNORECASE).replace(',', '').strip()
        for fmt in (
            '%Y-%m-%d', '%d-%m-%Y', '%d/%m/%Y', '%m/%d/%Y',
            '%B %d %Y', '%b %d %Y', '%d %B %Y', '%d %b %Y'
        ):
            try:
                dt = datetime.strptime(clean_date_str, fmt)
                deadline_val = dt.strftime('%Y-%m-%d')
                break
            except ValueError:
                continue

    # Identify common employment types
    employment_type = "On-site"
    lower_content = content.lower()
    lower_subject = subject.lower()
    lower_combined = f"{lower_subject} {lower_content}"

    if "remote" in lower_content:
        employment_type = "Remote"
    elif "hybrid" in lower_content:
        employment_type = "Hybrid"
    elif "part-time" in lower_content or "part time" in lower_content:
        employment_type = "Part-time"
    elif "full-time" in lower_content or "full time" in lower_content:
        employment_type = "Full-time"

    # Identify stipend hints
    stipend_val = ""
    stipend_match = re.search(r'(?:stipend|salary|remuneration|allowance)[:\s]+([^\n\r,.]+)', content, re.IGNORECASE)
    if stipend_match:
        stipend_val = stipend_match.group(1).strip()
    elif "unpaid" in lower_content:
        stipend_val = "Unpaid"

    # Classification: Determine if this is truly an internship (Scenario 4)
    # If explicitly titled full-time permanent role without intern reference, flag as not an internship
    is_non_internship = (
        ('full-time software engineer' in lower_combined or 'full time software engineer' in lower_combined) or
        ('permanent job' in lower_combined or 'career opportunity: full-time' in lower_combined) or
        ('full-time' in lower_subject and 'intern' not in lower_combined)
    )
    is_intern = not is_non_internship and any(
        w in lower_combined for w in ['intern', 'internship', 'trainee', 'fellowship', 'apprenticeship']
    )

    # Extract company and position from subject
    company_name = ""
    position = subject.strip()

    if ":" in subject:
        parts = subject.split(":", 1)
        company_name = parts[0].strip()
        position = parts[1].strip()
    elif " - " in subject:
        parts = subject.split(" - ", 1)
        company_name = parts[0].strip()
        position = parts[1].strip()
    else:
        comp_match = re.search(r'(?:at|with|for)\s+([A-Za-z0-9\s&.,]+)', subject, re.IGNORECASE)
        if comp_match:
            company_name = comp_match.group(1).strip()
            position = re.split(r'\s+(?:at|with|for)\s+', subject, flags=re.IGNORECASE)[0].strip()
        else:
            # Check known company tokens at start of subject
            known_companies = [
                'ABC Technologies', 'Grameenphone', 'BASH', 'foodpanda', 'NNC', 'TechNova'
            ]
            for comp in known_companies:
                if subject.lower().startswith(comp.lower()):
                    company_name = comp
                    remainder = subject[len(comp):].strip(" -:")
                    if remainder:
                        position = remainder
                    break

    return {
        "category": "internship" if is_intern else "other",
        "is_internship": is_intern,
        "company_name": company_name,
        "position": position,
        "description": content.strip()[:1000],
        "eligibility": "",
        "required_skills": [],
        "location": "Dhaka, Bangladesh" if "dhaka" in lower_content else "",
        "employment_type": employment_type,
        "stipend": stipend_val,
        "application_deadline": deadline_val,
        "application_url": application_url,
        "application_email": application_email,
        "application_instructions": "Please review the original notice details to complete application.",
        "source_title": subject.strip(),
        "extraction_notes": ["Extracted via fallback parser. Please verify and fill missing fields manually."]
    }


def extract_internship_with_gemini(
    email_subject: str,
    email_content: str,
    source_link: str = ""
) -> Tuple[str, Dict[str, Any]]:
    """
    Uses Google Gemini API to extract structured internship information.
    Returns: (status: str, result_dict: dict)
    Status values: 'success', 'partial', 'not_internship', 'failed'
    """
    clean_subject = sanitize_input_text(email_subject)
    clean_content = sanitize_input_text(email_content)

    api_key = os.getenv("GEMINI_API_KEY")
    model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    if not api_key:
        logger.warning("GEMINI_API_KEY not configured. Invoking heuristic fallback extractor.")
        fallback = heuristic_fallback_extractor(clean_subject, clean_content, source_link)
        status = "partial" if fallback.get("is_internship") else "not_internship"
        fallback["extraction_notes"].append("GEMINI_API_KEY is not set in .env. Admin review required.")
        return status, fallback

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)

        prompt = f"""You are an expert AI system extracting university internship notices from Career Development Center (CDC) emails.

Analyze the following CDC email carefully:

SUBJECT: {clean_subject}
SOURCE LINK: {source_link}
CONTENT:
{clean_content}

Your tasks:
1. Determine whether this notice represents a real internship or traineeship opportunity.
2. If it is NOT an internship (e.g. seminar, webinar, course, general news), set is_internship=false and explain in extraction_notes.
3. If it IS an internship, extract structured data.
4. STRICT COMPLIANCE: NEVER hallucinate or invent information. If deadline, stipend, company, or skills are not clearly stated, leave them null, empty string, or empty list.
5. Return ONLY a valid JSON object matching the schema below.

Target JSON Schema:
{{
  "category": "internship",
  "is_internship": true,
  "company_name": "Exact company name or empty string",
  "position": "Internship role / title or empty string",
  "description": "Comprehensive summary of the role and responsibilities",
  "eligibility": "Academic criteria, semester, department or CGPA requirements",
  "required_skills": ["List", "of", "explicit", "skills"],
  "location": "Job location / city or empty string",
  "employment_type": "Full-time / Part-time / Remote / On-site / Hybrid",
  "stipend": "Stipend amount or 'Unpaid' or empty string",
  "application_deadline": "YYYY-MM-DD or null",
  "application_url": "Direct application URL or empty string",
  "application_email": "Contact or application email or empty string",
  "application_instructions": "Steps to apply (CV submission, portal, email subject format)",
  "source_title": "{clean_subject}",
  "extraction_notes": ["Any pertinent observations regarding missing fields"]
}}
"""

        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1,
            )
        )

        response_text = response.text.strip()
        # Parse JSON
        extracted_data = json.loads(response_text)

        # Validate core fields
        if not isinstance(extracted_data, dict):
            raise ValueError("Gemini response is not a JSON object")

        is_intern = extracted_data.get("is_internship", True)
        if not is_intern:
            return "not_internship", extracted_data

        # Normalize date format if present
        deadline_str = extracted_data.get("application_deadline")
        if deadline_str:
            try:
                datetime.strptime(deadline_str, "%Y-%m-%d")
            except (ValueError, TypeError):
                extracted_data["application_deadline"] = None
                extracted_data.setdefault("extraction_notes", []).append("Deadline was not in YYYY-MM-DD format and was reset.")

        return "success", extracted_data

    except Exception as exc:
        logger.error(f"Error during Gemini extraction: {type(exc).__name__}: {str(exc)}")
        fallback = heuristic_fallback_extractor(clean_subject, clean_content, source_link)
        fallback["extraction_notes"].append(f"Gemini API error ({type(exc).__name__}). Fallback extraction used.")
        return "partial", fallback
