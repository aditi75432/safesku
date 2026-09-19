from pathlib import Path
import sys

# Make the repository root importable when pytest is launched from nested test directories.
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pandas as pd

from scripts.build_amazon_linkage_model_benchmark import (
    FEATURES,
    add_text_features,
    norm_text,
    rule_predictions,
)


def test_norm_text_is_stable():
    assert norm_text("Thompson's® WaterSeal 5-gal.") == "thompson s waterseal 5 gal"


def test_add_text_features_detects_exact_model_and_brand_overlap():
    df = pd.DataFrame(
        [
            {
                "cpsc_product_name": "Acme Turbo Heater",
                "amazon_title": "Acme Turbo Heater Model HX-10",
                "amazon_brand": "Acme",
                "amazon_manufacturer": "Acme Corp",
                "amazon_model": "HX-10",
                "exact_upc": 0,
                "shared_product_token_count": 3,
                "product_token_jaccard": 0.50,
            }
        ]
    )
    out = add_text_features(df)
    assert out.loc[0, "model_exact_in_title"] == 1.0
    assert out.loc[0, "cpsc_brand_like_token_in_amazon_title"] == 1.0
    assert out.loc[0, "title_sequence_similarity"] > 0.5


def test_rule_predictions_keep_exact_upc_as_match():
    df = pd.DataFrame(
        [
            {
                "exact_upc": 1,
                "shared_product_token_count": 0,
                "product_token_jaccard": 0.0,
                "title_sequence_similarity": 0.0,
            },
            {
                "exact_upc": 0,
                "shared_product_token_count": 3,
                "product_token_jaccard": 0.25,
                "title_sequence_similarity": 0.5,
            },
        ]
    )
    pred = rule_predictions(df, "token_similarity")
    assert pred.tolist() == [1, 1]


def test_feature_policy_contains_no_identity_or_annotation_metadata():
    forbidden = {
        "review_id",
        "cpsc_recall_number",
        "amazon_parent_asin",
        "reviewer_notes",
        "adjudicator",
    }
    assert forbidden.isdisjoint(FEATURES)
