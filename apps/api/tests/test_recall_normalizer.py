from app.services.recalls.normalizer import normalize_recall

def test_normalize_cpsc_recall() -> None:
    raw = {
        "RecallID": 12345, "RecallNumber": "26-123", "RecallDate": "2026-09-10",
        "LastPublishDate": "2026-09-10T12:30:00", "Title": "Example Product Recall",
        "Description": "Example description", "URL": "https://example.com/recall",
        "ConsumerContact": "1-800-555-0100",
        "Products": {"Product": {"Name": "Example Heater", "Model": "EH-100", "Type": "Heating", "CategoryID": "42", "NumberOfUnits": "About 10,605 (In addition, 342 were sold in Canada)",}},
        "Manufacturers": {"Manufacturer": {"Name": "Example Inc.", "CompanyID": "C123"}},
        "Hazards": {"Hazard": {"Name": "Fire", "HazardType": "Fire", "HazardTypeID": "7"}},
        "ProductUPCs": {"ProductUPC": {"UPC": "012345678901"}},
        "Remedies": {"Remedy": {"Name": "Stop using the product"}},
        "RemedyOptions": {"RemedyOption": {"Option": "Refund"}},
     
    }
    record = normalize_recall(raw)
    assert record.source == "cpsc"
    assert record.source_record_id == "12345"
    assert record.recall_number == "26-123"
    assert record.products[0].model == "EH-100"
    assert record.manufacturers[0].name == "Example Inc."
    assert record.hazards[0].name == "Fire"
    assert record.product_upcs == ["012345678901"]
    assert record.remedy_options[0].option == "Refund"
    assert record.products[0].number_of_units == (
    "About 10,605 (In addition, 342 were sold in Canada)"
)
