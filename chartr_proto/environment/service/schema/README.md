# Pinned schema provenance

Official HL7 FHIR R4 **4.0.1**, from
[the permanent R4 downloads page](https://hl7.org/fhir/R4/downloads.html).
Downloaded archive: [fhir.schema.json.zip](https://hl7.org/fhir/R4/fhir.schema.json.zip).
The unchanged archive member `fhir.schema.json` is vendored here.

SHA-256: `2230406893b4cf002a4ee1e5e2bbeca22ac5d2d4931b3e9ef7b9594bbc376a01`.
`fhir.py` verifies this digest and uses jsonschema 4.26.0's Draft6Validator with the
resource's definition as the entry point. The official schema contains its own
FHIR resource and primitive definitions. It is not a claim of complete FHIR
conformance or validation of all terminology/FHIRPath constraints.

Mapping references: [Task](https://hl7.org/fhir/R4/task.html),
[DocumentReference](https://hl7.org/fhir/R4/documentreference.html),
[MedicationRequest](https://hl7.org/fhir/R4/medicationrequest.html),
[ServiceRequest](https://hl7.org/fhir/R4/servicerequest.html).
The custom `chartr.example` URLs are local simulation definitions, not HL7 standards.
