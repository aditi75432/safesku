from enum import StrEnum


class DataSource(StrEnum):
    CPSC = "cpsc"
    SAFER_PRODUCTS = "saferproducts"
    AMAZON_REVIEWS_2023 = "amazon_reviews_2023"


class EvidenceType(StrEnum):
    RECALL = "recall"
    INCIDENT_REPORT = "incident_report"
    CONSUMER_REVIEW = "consumer_review"
    PRODUCT_METADATA = "product_metadata"
    HAZARD_STATEMENT = "hazard_statement"
    INJURY_STATEMENT = "injury_statement"
    REMEDY_STATEMENT = "remedy_statement"


class MatchMethod(StrEnum):
    EXACT_IDENTIFIER = "exact_identifier"
    LEXICAL = "lexical"
    SEMANTIC = "semantic"
    ATTRIBUTE = "attribute"
    HYBRID = "hybrid"


class MatchDecision(StrEnum):
    MATCH = "match"
    POSSIBLE_MATCH = "possible_match"
    NO_MATCH = "no_match"
