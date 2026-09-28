"""Task 3 authored cohort (PRIVATE). Never copy into any environment/ directory.

Each patient has one syphilis episode. `records` is the chart as the clinic holds it; `facts` is the
clinical model a competent reviewer extracts from it under the CDC 2021 STI Treatment Guidelines; `truth`
is the authored disposition for every candidate that is not a silent not_an_issue. qa/task3_rules.py
recomputes every disposition from `facts` and must agree with `truth`.

Record tuples (rendered by qa/build_task3.py):
  ('note', day, hhmm, role, author, doc_type, text)
  ('outside', day, facility, text)                  scanned record received from another facility
  ('condition', day, text, recorder)                staging diagnosis on the diagnosis list
  ('allergy', day, substance, reaction)
  ('rpr', day, result, opts)                        result: '1:16' / 'NR' / None when pending or rejected
  ('trep', day, result)                             treponemal antibody (TP-PA)
  ('hcg', day, result, opts)                        result: 'positive' / 'negative' / None when pending
  ('bpg', day, dose_text, performer, comment)       clinic administration of benzathine penicillin G
  ('med', day, drug_text, dose_text, performer, comment, status)   other clinic administration
  ('dispense', day, drug_text, qty, days, sig, note)
  ('lab', day, test, result)                        unrelated routine laboratory result
"""
EVAL = '2026-09-24'
ISSUES = ('INADEQUATE_TREATMENT', 'FOLLOW_UP_OVERDUE', 'MISFILED_RESULT', 'PREGNANCY_TREATMENT_INADEQUATE')
ADQ, FUP, MIS, PRG = ISSUES
PEND, OUT, CONF = 'RESULT_PENDING', 'OUTSIDE_RECORD_NOT_RECEIVED', 'UNRESOLVED_SOURCE_CONFLICT'

# A non-cohort clinic patient named by one laboratory accessioning entry.
EXTERNAL = {'mrn': '40718826', 'dob': '1990-03-02', 'name': 'NGUYEN, THAO'}

DR = ['Dr. Imani Shaw', 'Dr. Noah Patel', 'Dr. Elias Green', 'Dr. Rosa Alvarez']
RN = ['Ana Ruiz, RN', 'Jordan Lee, RN', 'Mina Cho, RN', 'Sam Okafor, LPN']
PHARM = 'Priya Desai, PharmD'
LAB = 'Clinical Laboratory, M. Ortiz MLS'


def routine(day, who, text):
    return ('note', day, '0930', 'nurse', who, 'Nursing note', text)


PATIENTS = [
    # ---------------------------------------------------------------- 1: stage never recorded, latent, no
    # evidence of infection within 12 months -> unknown duration -> one dose is inadequate.
    dict(key='p01', name='Dana Whitfield', sex='female', dob='1984-06-19', dx='2026-03-10',
         records=[
             ('lab', '2026-03-10', 'HIV-1/2 Ag/Ab', 'Nonreactive'),
             ('trep', '2026-03-10', 'reactive'),
             ('rpr', '2026-03-10', '1:16', {}),
             ('hcg', '2026-03-10', 'negative', {}),
             ('note', '2026-03-10', '1015', 'clinician', DR[0], 'Progress note',
              'New pt referred by her dentist after a reactive screen on a pre-op panel. Denies sores, rash, '
              'hair loss, visual or hearing changes. No prior syphilis testing she knows of; first STI visit. '
              'One partner, monogamous 6 yrs, partner not yet tested. Exam: no genital or oral lesions, no rash, '
              'no lymphadenopathy, neuro grossly intact.\nRPR 1:16, TP-PA reactive. HIV neg. hCG neg.\n'
              'Plan: Bicillin L-A today. Partner referral card given. Will call with plan for remaining care.'),
             ('bpg', '2026-03-10', '2.4 million units IM', RN[0], 'R and L ventrogluteal, 1.2 MU each side. Tolerated.'),
             ('note', '2026-03-24', '1410', 'nurse', RN[1], 'Telephone encounter',
              'Called pt re: partner - partner seen at county clinic, results pending per pt. Pt asked if she is '
              '"done"; advised provider will review. No further appts scheduled at this time.'),
         ],
         facts=dict(stage='late_latent', stage_recorded=False),
         wrong={'fill_stage': dict(stage='early_latent')},
         truth={ADQ: ('confirmed', None)}, kinds={ADQ: 'inference'},
         requests={ADQ: 'Pharmacy QA: one Bicillin injection documented for this episode. Please review whether treatment is complete.'},
         gaps={'stage_unrecorded': (ADQ, FUP)}),

    # ---------------------------------------------------------------- 2: secondary on exam, treated only
    # with azithromycin -> inadequate for any stage.
    dict(key='p02', name='Marcus Bell', sex='male', dob='1996-01-08', dx='2025-11-04',
         records=[
             ('trep', '2025-11-04', 'reactive'),
             ('rpr', '2025-11-04', '1:64', {}),
             ('note', '2025-11-04', '1640', 'clinician', 'Dr. Kelly Moran (locum)', 'Walk-in visit',
              'c/o rash x 2 wks, not itchy. Diffuse maculopapular rash trunk, palms and soles. Shallow oral '
              'ulcer. RPR 1:64 reactive; trep reactive. Pt states "can\'t do shots", very needle averse, left '
              'the room when the Bicillin was brought in. Gave azithromycin 2 g PO in clinic as alternative. '
              'F/u 2 wk.'),
             ('med', '2025-11-04', 'Azithromycin 500 mg tab', '2 g (4 tabs) PO', RN[2], 'Observed swallowing. No GI upset.', 'completed'),
             ('note', '2025-11-19', '1105', 'clinician', DR[1], 'Progress note',
              'F/u: rash much improved, faint on palms. Pt feels well. Discussed. Pt again declines injection. '
              'Recheck RPR at 6 mo.'),
             ('rpr', '2026-05-12', '1:16', {}),
         ],
         facts=dict(stage='secondary', stage_recorded=False),
         wrong={'fill_stage': dict(stage='early_latent'), 'default_late': dict(stage='late_latent')},
         truth={ADQ: ('confirmed', None)}, kinds={ADQ: 'inference'},
         gaps={'stage_unrecorded': (ADQ, FUP)}),

    # ---------------------------------------------------------------- 3: recorded as unknown duration.
    dict(key='p03', name='Terrence Obi', sex='male', dob='1971-09-30', dx='2025-09-15',
         records=[
             ('condition', '2025-09-15', 'Latent syphilis, unknown duration', DR[2]),
             ('trep', '2025-09-15', 'reactive'),
             ('rpr', '2025-09-15', '1:8', {}),
             ('bpg', '2025-09-15', '2.4 million units IM', RN[3], 'L gluteal. Tolerated well.'),
             ('note', '2025-09-15', '1120', 'clinician', DR[2], 'Progress note',
              'Asymptomatic. Last neg test unknown, pt thinks "a few years ago" elsewhere, no records. '
              'Latent, duration unknown. Bicillin weekly x3, first today. RTC 9/22 and 9/29.'),
             ('note', '2025-09-22', '1630', 'nurse', RN[1], 'Telephone encounter', 'No show for injection #2. LVM to call back.'),
             ('note', '2025-09-30', '0915', 'nurse', RN[1], 'Telephone encounter', 'No show 9/29. Second VM left. Letter mailed.'),
             ('rpr', '2026-03-20', '1:4', {}),
         ],
         facts=dict(stage='late_latent'),
         truth={ADQ: ('confirmed', None)}, kinds={ADQ: 'real'}),

    # ---------------------------------------------------------------- 4: 18-day gap in a late latent series.
    dict(key='p04', name='Harold Pruitt', sex='male', dob='1965-04-12', dx='2025-06-02',
         records=[
             ('condition', '2025-06-02', 'Late latent syphilis', DR[3]),
             ('trep', '2025-06-02', 'reactive'),
             ('rpr', '2025-06-02', '1:4', {}),
             ('bpg', '2025-06-02', '2.4 million units IM', RN[0], 'R gluteal.'),
             ('bpg', '2025-06-09', '2.4 million units IM', RN[0], 'L gluteal.'),
             ('note', '2025-06-17', '1015', 'nurse', RN[2], 'Telephone encounter',
              'Pt called to cancel 6/16 injection, out of state for family funeral, back end of next week.'),
             ('bpg', '2025-06-27', '2.4 million units IM', RN[2], 'R gluteal. Pt back from travel.'),
             ('note', '2025-06-27', '1120', 'nurse', RN[2], 'Nursing note', 'Third Bicillin given today. Series complete per pt. Next RPR in 6 mo.'),
             ('rpr', '2025-12-05', '1:2', {}),
             ('rpr', '2026-06-15', '1:2', {}),
         ],
         facts=dict(stage='late_latent'),
         truth={ADQ: ('confirmed', None)}, kinds={ADQ: 'real'}),

    # ---------------------------------------------------------------- 5: charted 1.2 MU, corrected by the
    # administering nurse to the full 2.4 MU; declined an unnecessary second dose.
    dict(key='p05', name='Lucia Ferreira', sex='female', dob='1999-11-23', dx='2026-04-07',
         records=[
             ('rpr', '2025-10-01', 'NR', {}),
             ('trep', '2026-04-07', 'reactive'),
             ('rpr', '2026-04-07', '1:8', {}),
             ('hcg', '2026-04-07', 'negative', {}),
             ('condition', '2026-04-07', 'Early latent syphilis', DR[0]),
             ('bpg', '2026-04-07', '1.2 million units IM', RN[0], 'R ventrogluteal.'),
             ('note', '2026-04-07', '1545', 'nurse', RN[0], 'Nursing note - late entry',
              'Late entry re: Bicillin today. MAR shows 1.2 million units; that is the per-syringe amount. Two '
              '1.2 MU syringes were given, one each side, 2.4 million units total as ordered. Documentation '
              'error on my part.'),
             ('note', '2026-04-14', '1030', 'clinician', DR[0], 'Telephone encounter',
              'Pt asked whether she needs a second shot like her cousin had. Explained single dose is treatment for her '
              'stage. She declined coming in. Repeat RPR at 6 and 12 months.'),
         ],
         facts=dict(stage='early_latent', doses=[('2026-04-07', 'bpg')]),
         wrong={'structured_only': dict(doses=[('2026-04-07', 'bpg_half')])},
         kinds={ADQ: 'nonissue'}),

    # ---------------------------------------------------------------- 6: MAR 2.4 MU vs pharmacy 1.2 MU, no
    # author correction.
    dict(key='p06', name='Andre Castillo', sex='male', dob='1992-07-04', dx='2026-05-19',
         records=[
             ('rpr', '2025-12-02', 'NR', {}),
             ('trep', '2026-05-19', 'reactive'),
             ('rpr', '2026-05-19', '1:32', {}),
             ('condition', '2026-05-19', 'Early latent syphilis', DR[1]),
             ('bpg', '2026-05-19', '2.4 million units IM', RN[2], 'L ventrogluteal.'),
             ('dispense', '2026-05-19', 'Bicillin L-A 1,200,000 units/2 mL prefilled syringe', 1, 1,
              'Administer IM in clinic', 'Released to clinic nurse 13:05.'),
             ('note', '2026-05-19', '1640', 'pharmacist', PHARM, 'Pharmacy note',
              'End-of-day reconciliation: one 1.2 MU Bicillin L-A syringe released for this patient today. No '
              'second syringe pulled from the clinic stock for him per the cabinet log.'),
         ],
         facts=dict(stage='early_latent'),
         unknown=dict(code=CONF, kind='conflict', best='mar', latest='pharmacy',
                      options={'mar': dict(doses=[('2026-05-19', 'bpg')]),
                               'pharmacy': dict(doses=[('2026-05-19', 'bpg_half')])}),
         truth={ADQ: ('cannot_determine', CONF)}, kinds={ADQ: 'undeterminable'},
         gaps={'conflict': (ADQ,)}),

    # ---------------------------------------------------------------- 7: outside letter says secondary, clinic
    # says early latent: both early, one dose adequate either way.
    dict(key='p07', name='Keisha Morrow', sex='female', dob='1990-02-14', dx='2026-02-17',
         records=[
             ('outside', '2026-02-03', 'Northside Urgent Care',
              'NORTHSIDE URGENT CARE - REFERRAL\nRe: Keisha Morrow  DOB 02/14/1990\nSeen 2/2/26 for rash. '
              'Maculopapular rash palms/soles. RPR reactive 1:32 (Quest). Impression: secondary syphilis. Unable '
              'to treat on site (no Bicillin stocked). Referred to your clinic for treatment.\nJ. Park, PA-C'),
             ('trep', '2026-02-17', 'reactive'),
             ('rpr', '2026-02-17', '1:32', {}),
             ('hcg', '2026-02-17', 'negative', {}),
             ('condition', '2026-02-17', 'Early latent syphilis', DR[3]),
             ('note', '2026-02-17', '0950', 'clinician', DR[3], 'Progress note',
              'Referred from Northside UC. Today no rash visible, no lesions; pt says rash faded last week. '
              'Assessment: early latent syphilis. Bicillin L-A today.'),
             ('bpg', '2026-02-17', '2.4 million units IM', RN[1], 'R gluteal.'),
             ('rpr', '2026-08-20', '1:4', {}),
         ],
         facts=dict(stage='early_latent'),
         unknown=dict(code=CONF, kind='conflict', best='clinic', latest='clinic',
                      options={'clinic': dict(stage='early_latent'), 'outside': dict(stage='secondary')}),
         kinds={ADQ: 'relevance'}, gaps={'conflict': (ADQ, FUP)}),

    # ---------------------------------------------------------------- 8: late latent, doses 2-3 reportedly
    # given elsewhere, never received.
    dict(key='p08', name='Renee Salazar', sex='female', dob='1979-12-01', dx='2026-01-20',
         records=[
             ('condition', '2026-01-20', 'Late latent syphilis', DR[1]),
             ('trep', '2026-01-20', 'reactive'),
             ('rpr', '2026-01-20', '1:2', {}),
             ('hcg', '2026-01-20', 'negative', {}),
             ('bpg', '2026-01-20', '2.4 million units IM', RN[3], 'R gluteal. #1 of 3.'),
             ('note', '2026-01-29', '1115', 'nurse', RN[3], 'Telephone encounter',
              'Pt called. Moved in w/ her sister in Riverton, 40 min away, no car. Says she got her 2nd Bicillin '
              'shot at Eastside Community Health on Tues 1/27 and they scheduled the 3rd there for 2/3. Asked '
              'pt to sign ROI; ROI signed via portal and faxed to Eastside medical records for injection records.'),
             ('note', '2026-03-02', '1340', 'nurse', RN[3], 'Records request',
              '2nd request faxed to Eastside Community Health medical records for Bicillin administration records '
              '(Jan-Feb 2026). No response to first request.'),
             ('rpr', '2026-07-22', '1:1', {}),
         ],
         facts=dict(stage='late_latent'),
         unknown=dict(code=OUT, kind='outside', best='given', absent='not_given',
                      options={'given': dict(doses=[('2026-01-20', 'bpg'), ('2026-01-27', 'bpg'), ('2026-02-03', 'bpg')]),
                               'not_given': dict(doses=[('2026-01-20', 'bpg')])}),
         truth={ADQ: ('cannot_determine', OUT)}, kinds={ADQ: 'undeterminable'},
         gaps={'outside': (ADQ,)}),

    # ---------------------------------------------------------------- 9: outside injections received; 12-mo
    # specimen hemolyzed and recollected inside the window.
    dict(key='p09', name='Gerald Hwang', sex='male', dob='1958-05-27', dx='2025-04-14',
         records=[
             ('condition', '2025-04-14', 'Late latent syphilis', DR[2]),
             ('trep', '2025-04-14', 'reactive'),
             ('rpr', '2025-04-14', '1:4', {}),
             ('bpg', '2025-04-14', '2.4 million units IM', RN[1], 'L gluteal.'),
             ('note', '2025-04-16', '0900', 'nurse', RN[1], 'Telephone encounter',
              'Pt\'s daughter called: bus route cut, he can\'t get here weekly. County Health STD clinic is walking '
              'distance. Coordinated w/ County; they will give injections 2 and 3. ROI faxed.'),
             ('outside', '2025-05-06', 'County Health Department STD Clinic',
              'COUNTY HEALTH DEPT - STD CLINIC  FAX\nPatient: HWANG, GERALD  DOB 05/27/1958\nMedication '
              'administration record:\n 04/21/2025  Bicillin L-A 2.4 MU IM  L glut  KT RN\n 04/28/2025  Bicillin '
              'L-A 2.4 MU IM  R glut  KT RN\nSeries complete (3 of 3 incl. dose given at referring clinic 04/14).'),
             ('rpr', '2025-10-20', '1:2', {}),
             ('rpr', '2026-04-02', None, {'status': 'rejected', 'comment': 'Specimen grossly hemolyzed. Test not performed. Please recollect.'}),
             ('rpr', '2026-04-11', '1:1', {}),
         ],
         facts=dict(stage='late_latent', doses=[('2025-04-14', 'bpg'), ('2025-04-21', 'bpg'), ('2025-04-28', 'bpg')]),
         wrong={'structured_only': dict(doses=[('2025-04-14', 'bpg')])},
         kinds={ADQ: 'nonissue', FUP: 'nonissue'},
         requests={ADQ: 'Pharmacy QA: only one of three Bicillin doses is in our administration record. Please review.'},
         gaps={'outside_received': (ADQ,)}),

    # ---------------------------------------------------------------- 10: 2019 records never received (irrelevant);
    # 12-month RPR never obtained.
    dict(key='p10', name='Joel Ramirez', sex='male', dob='1987-08-09', dx='2025-02-24',
         records=[
             ('trep', '2025-02-24', 'reactive'),
             ('rpr', '2025-02-24', '1:8', {}),
             ('condition', '2025-02-24', 'Early latent syphilis', DR[0]),
             ('note', '2025-02-24', '1400', 'clinician', DR[0], 'Progress note',
              'Here as a contact: partner dx\'d with primary syphilis 3 wks ago at this clinic. Pt asymptomatic, exam '
              'normal. States he had syphilis in 2019 in Houston and got "one shot"; records requested from Harris '
              'County Public Health. RPR 1:8. Early latent (partner with primary syphilis within the past year). '
              'Bicillin today.'),
             ('bpg', '2025-02-24', '2.4 million units IM', RN[0], 'R gluteal.'),
             ('rpr', '2025-09-02', '1:2', {}),
             ('note', '2026-02-10', '1000', 'nurse', RN[2], 'Outreach', '12-month RPR reminder: called x2, number not in service. Letter sent.'),
             ('note', '2026-03-20', '1000', 'nurse', RN[2], 'Outreach', 'Letter returned undeliverable.'),
         ],
         facts=dict(stage='early_latent'),
         unknown=dict(code=OUT, kind='outside', best='any', absent='any', options={'any': {}}),
         truth={FUP: ('confirmed', None)}, kinds={ADQ: 'relevance', FUP: 'real'},
         gaps={'outside': (ADQ,)}),

    # ---------------------------------------------------------------- 11: 12-month specimen collected in the
    # window, result still pending.
    dict(key='p11', name='Brianna Scott', sex='female', dob='2001-03-17', dx='2025-08-18',
         records=[
             ('trep', '2025-08-18', 'reactive'),
             ('rpr', '2025-08-18', '1:32', {}),
             ('hcg', '2025-08-18', 'negative', {}),
             ('condition', '2025-08-18', 'Primary syphilis', DR[3]),
             ('note', '2025-08-18', '1210', 'clinician', DR[3], 'Progress note', 'Painless ulcer labia majora x 10 d. Primary syphilis. BPG today.'),
             ('bpg', '2025-08-18', '2.4 million units IM', RN[3], 'L ventrogluteal.'),
             ('rpr', '2026-02-24', '1:4', {}),
             ('rpr', '2026-09-08', None, {'status': 'pending', 'comment': 'Received at reference laboratory. Result to follow.'}),
         ],
         facts=dict(stage='primary'),
         kinds={FUP: 'relevance'},
         requests={FUP: 'Quality report: 12-month RPR has no result on file. Please review whether follow-up is overdue.'},
         gaps={'pending_rpr': (FUP,)}),

    # ---------------------------------------------------------------- 12: no staging entry but secondary on
    # exam: no 24-month test is recommended.
    dict(key='p12', name='Victor Nakamura', sex='male', dob='1993-10-05', dx='2024-05-06',
         records=[
             ('trep', '2024-05-06', 'reactive'),
             ('rpr', '2024-05-06', '1:128', {}),
             ('note', '2024-05-06', '1515', 'clinician', DR[1], 'Progress note',
              'Rash x 3 wks. Papulosquamous eruption trunk and palms, mucous patches on the tongue, patchy '
              'alopecia. RPR 1:128, TP-PA +. Bicillin L-A given. Pt counseled; partner notification.'),
             ('bpg', '2024-05-06', '2.4 million units IM', RN[1], 'R gluteal.'),
             ('rpr', '2024-11-12', '1:8', {}),
             ('rpr', '2025-05-20', '1:2', {}),
             ('note', '2025-05-20', '1000', 'clinician', DR[1], 'Progress note', 'RPR 1:2, fourfold+ decline. Discharged from syphilis follow-up.'),
         ],
         facts=dict(stage='secondary', stage_recorded=False),
         wrong={'fill_stage': dict(stage='late_latent'), 'default_late': dict(stage='late_latent')},
         kinds={ADQ: 'relevance', FUP: 'inference'},
         gaps={'stage_unrecorded': (ADQ, FUP)}),

    # ---------------------------------------------------------------- 13: 12-month RPR reportedly drawn at a
    # PCP, never received.
    dict(key='p13', name='Olivia Grant', sex='female', dob='1995-05-30', dx='2025-07-07',
         records=[
             ('rpr', '2025-02-11', 'NR', {}),
             ('trep', '2025-07-07', 'reactive'),
             ('rpr', '2025-07-07', '1:16', {}),
             ('hcg', '2025-07-07', 'negative', {}),
             ('condition', '2025-07-07', 'Early latent syphilis', DR[2]),
             ('bpg', '2025-07-07', '2.4 million units IM', RN[0], 'R ventrogluteal.'),
             ('rpr', '2026-01-15', '1:4', {}),
             ('note', '2026-08-12', '1500', 'nurse', RN[1], 'Telephone encounter',
              'Called for overdue 12-month RPR. Pt says she already had "the syphilis blood test" at her PCP '
              '(Dr. Lin, Maple Family Medicine) sometime in July with her annual labs. Faxed request to Maple '
              'Family Medicine for the result.'),
         ],
         facts=dict(stage='early_latent'),
         unknown=dict(code=OUT, kind='outside', best='drawn', absent='not_drawn',
                      options={'drawn': dict(extra_fu=[('2026-07-15', 'final')]), 'not_drawn': {}}),
         truth={FUP: ('cannot_determine', OUT)}, kinds={FUP: 'undeterminable'},
         gaps={'outside': (FUP,)}),

    # ---------------------------------------------------------------- 14: the 12-month RPR in this chart is
    # p15's (collection record and accessioning both say so).
    dict(key='p14', name='Samuel Ortega', sex='male', dob='1983-01-26', dx='2025-06-09',
         records=[
             ('trep', '2025-06-09', 'reactive'),
             ('rpr', '2025-06-09', '1:64', {}),
             ('condition', '2025-06-09', 'Primary syphilis', DR[0]),
             ('bpg', '2025-06-09', '2.4 million units IM', RN[2], 'L gluteal.'),
             ('rpr', '2025-12-11', '1:8', {}),
             ('rpr', '2026-06-16', 'NR', {'owner': 'p15', 'collector': RN[3]}),
         ],
         facts=dict(stage='primary'),
         truth={MIS: ('confirmed', None), FUP: ('confirmed', None)}, kinds={MIS: 'real', FUP: 'real'}),

    dict(key='p15', name='Samantha Ortiz', sex='female', dob='1998-08-13', dx='2025-06-23',
         records=[
             ('rpr', '2025-01-06', 'NR', {}),
             ('trep', '2025-06-23', 'reactive'),
             ('rpr', '2025-06-23', '1:8', {}),
             ('hcg', '2025-06-23', 'negative', {}),
             ('condition', '2025-06-23', 'Early latent syphilis', DR[2]),
             ('bpg', '2025-06-23', '2.4 million units IM', RN[3], 'R gluteal.'),
             ('rpr', '2025-12-29', '1:2', {}),
             ('note', '2026-06-16', '1045', 'nurse', RN[3], 'Nursing note', 'Here for 12-month labs. RPR drawn, pt tolerated.'),
         ],
         facts=dict(stage='early_latent'),
         kinds={FUP: 'nonissue'},
         requests={FUP: 'Quality report: no 12-month RPR result in this chart. Please review whether follow-up is overdue.'}),

    # ---------------------------------------------------------------- 16: collection label says p16, lab
    # accessioning says another patient; it is the only 24-month specimen.
    dict(key='p16', name='Walter Greene', sex='male', dob='1960-11-18', dx='2024-08-12',
         records=[
             ('condition', '2024-08-12', 'Late latent syphilis', DR[3]),
             ('trep', '2024-08-12', 'reactive'),
             ('rpr', '2024-08-12', '1:8', {}),
             ('bpg', '2024-08-12', '2.4 million units IM', RN[0], 'R gluteal. 1/3.'),
             ('bpg', '2024-08-19', '2.4 million units IM', RN[0], 'L gluteal. 2/3.'),
             ('bpg', '2024-08-26', '2.4 million units IM', RN[0], 'R gluteal. 3/3.'),
             ('rpr', '2025-02-20', '1:4', {}),
             ('rpr', '2025-08-14', '1:2', {}),
             ('rpr', '2026-08-05', 'NR', {'accession_owner': 'EXTERNAL', 'collector': RN[1]}),
         ],
         facts=dict(stage='late_latent'),
         unknown=dict(code=CONF, kind='conflict', best='collection', latest='accession', chart='collection',
                      options={'collection': {}, 'accession': dict(fu_drop=['2026-08-05'], misfiled=True)}),
         truth={MIS: ('cannot_determine', CONF), FUP: ('cannot_determine', CONF)},
         kinds={MIS: 'undeterminable', FUP: 'undeterminable'},
         requests={MIS: 'Laboratory QA: possible identification discrepancy on the 8/5 RPR. Please review.'},
         gaps={'conflict': (MIS, FUP)}),

    # ---------------------------------------------------------------- 17: label shows former name; MRN/DOB match.
    dict(key='p17', name='Maria Reyes', former='GOMEZ, MARIA', sex='female', dob='1989-04-02', dx='2025-10-06',
         records=[
             ('trep', '2025-10-06', 'reactive'),
             ('rpr', '2025-10-06', '1:32', {}),
             ('hcg', '2025-10-06', 'negative', {}),
             ('condition', '2025-10-06', 'Primary syphilis', DR[1]),
             ('bpg', '2025-10-06', '2.4 million units IM', RN[2], 'R ventrogluteal.'),
             ('note', '2026-01-12', '0830', 'registration', 'Front desk (L. Ames)', 'Registration update',
              'Legal name change on file (court order scanned). Previous name: Maria Gomez. Updated demographics; MRN unchanged.'),
             ('rpr', '2026-04-08', '1:4', {'label_name': 'GOMEZ, MARIA'}),
         ],
         facts=dict(stage='primary'),
         kinds={MIS: 'nonissue'},
         requests={MIS: 'Laboratory QA: specimen label name does not match the current chart name for the 4/8 RPR. Please review.'}),

    # ---------------------------------------------------------------- 18: delivered elsewhere, record not received,
    # but a prenatal visit 47 days after the dose shows the pregnancy was ongoing.
    dict(key='p18', name='Jasmine Carter', sex='female', dob='1997-07-21', dx='2025-11-03',
         records=[
             ('rpr', '2025-08-18', 'NR', {}),
             ('note', '2025-08-18', '1000', 'clinician', DR[0], 'Prenatal intake', 'G2P1 at 11w2d by LMP. Routine prenatal labs incl. RPR.'),
             ('trep', '2025-11-03', 'reactive'),
             ('rpr', '2025-11-03', '1:16', {}),
             ('condition', '2025-11-03', 'Early latent syphilis', DR[0]),
             ('note', '2025-11-03', '1130', 'clinician', DR[0], 'Prenatal visit',
              '22w2d. RPR now reactive 1:16 (neg at intake 8/18), no symptoms. Early latent syphilis in pregnancy. '
              'Bicillin L-A today; partner referral.'),
             ('bpg', '2025-11-03', '2.4 million units IM', RN[1], 'L gluteal.'),
             ('rpr', '2025-12-20', '1:8', {}),
             ('note', '2025-12-20', '1015', 'clinician', DR[0], 'Prenatal visit', '28w6d. FH 29 cm, FHR 140s. Doing well. RPR repeated. Plans delivery at St. Luke\'s.'),
             ('note', '2026-03-09', '1400', 'nurse', RN[2], 'Telephone encounter',
              'Pt called to schedule postpartum f/u. Delivered at St. Luke\'s in February, baby "fine, got a shot '
              'too". Requested delivery and newborn records from St. Luke\'s HIM.'),
             ('rpr', '2026-05-11', '1:2', {}),
         ],
         facts=dict(stage='early_latent', pregnant=True),
         unknown=dict(code=OUT, kind='outside', best='feb', absent='feb',
                      options={'early': dict(delivery='2025-12-21'), 'feb': dict(delivery='2026-02-15'),
                               'late': dict(delivery='2026-03-08')}),
         kinds={PRG: 'relevance', ADQ: 'control'},
         gaps={'outside': (PRG,)}),

    # ---------------------------------------------------------------- 19: series started 3 weeks before the last
    # documented prenatal visit; delivery date unknown.
    dict(key='p19', name='Aaliyah Brooks', sex='female', dob='2000-12-09', dx='2026-01-05',
         records=[
             ('note', '2026-01-05', '0900', 'clinician', DR[3], 'Prenatal visit',
              'Transfer of care at 35w1d, no prior prenatal care. Prenatal labs today. RPR 1:4, TP-PA reactive; no '
              'prior testing on record. Latent syphilis of unknown duration in pregnancy. Bicillin L-A weekly x3, '
              'first today.'),
             ('trep', '2026-01-05', 'reactive'),
             ('rpr', '2026-01-05', '1:4', {}),
             ('condition', '2026-01-05', 'Latent syphilis, unknown duration', DR[3]),
             ('bpg', '2026-01-05', '2.4 million units IM', RN[0], 'R gluteal. 1 of 3.'),
             ('bpg', '2026-01-12', '2.4 million units IM', RN[0], 'L gluteal. 2 of 3.'),
             ('bpg', '2026-01-19', '2.4 million units IM', RN[0], 'R gluteal. 3 of 3.'),
             ('note', '2026-01-26', '1100', 'clinician', DR[3], 'Prenatal visit', '38w1d. Series completed 1/19. Cephalic, FHR 130s. L&D precautions. Plans Mercy General.'),
             ('note', '2026-02-20', '1600', 'nurse', RN[3], 'Telephone encounter',
              'Pt called. Delivered at Mercy General, baby had a workup there for syphilis and is home now. '
              'Requested maternal delivery records and newborn discharge summary from Mercy General.'),
             ('rpr', '2026-07-10', '1:1', {}),
         ],
         facts=dict(stage='late_latent', pregnant=True),
         unknown=dict(code=OUT, kind='outside', best='late', absent='undelivered',
                      options={'early': dict(delivery='2026-01-28'), 'late': dict(delivery='2026-02-12'),
                               'undelivered': dict(delivery=None)}),
         truth={PRG: ('cannot_determine', OUT)}, kinds={PRG: 'undeterminable', ADQ: 'control'},
         requests={PRG: 'Perinatal QA: confirm whether maternal treatment was adequate for this delivery.'},
         gaps={'outside': (PRG,)}),

    # ---------------------------------------------------------------- 20: penicillin anaphylaxis, doxycycline;
    # pregnancy test never resulted.
    dict(key='p20', name='Nadia Petrova', sex='female', dob='1994-09-12', dx='2026-06-15',
         records=[
             ('allergy', '2019-03-01', 'Penicillin', 'Anaphylaxis (throat swelling, hypotension) after amoxicillin 2019; ED visit.'),
             ('rpr', '2025-11-20', 'NR', {}),
             ('trep', '2026-06-15', 'reactive'),
             ('rpr', '2026-06-15', '1:16', {}),
             ('hcg', '2026-06-15', None, {'comment': 'Specimen forwarded to reference laboratory.'}),
             ('condition', '2026-06-15', 'Early latent syphilis', DR[2]),
             ('note', '2026-06-15', '1150', 'clinician', DR[2], 'Progress note',
              'Asymptomatic, RPR neg 11/2025. Early latent. Severe PCN allergy (anaphylaxis). LMP uncertain, '
              'irregular cycles; serum hCG sent. Doxycycline 100 mg BID x 14 days started today. Discussed '
              'desensitization if needed.'),
             ('dispense', '2026-06-15', 'Doxycycline hyclate 100 mg capsule', 28, 14, 'Take 1 capsule by mouth twice daily for 14 days', ''),
             ('note', '2026-07-02', '1300', 'nurse', RN[1], 'Telephone encounter', 'Pt finished doxycycline yesterday, no missed doses.'),
         ],
         facts=dict(stage='early_latent', allergy=True),
         unknown=dict(code=PEND, kind='pending', best='not_pregnant', negative='not_pregnant',
                      options={'pregnant': dict(pregnant=True), 'not_pregnant': dict(pregnant=False)}),
         truth={ADQ: ('cannot_determine', PEND), PRG: ('cannot_determine', PEND)},
         kinds={ADQ: 'undeterminable', PRG: 'undeterminable'},
         gaps={'pending_hcg': (ADQ, PRG)}),

    # ---------------------------------------------------------------- 21: late latent, one dose then lost;
    # later hCG pending.
    dict(key='p21', name='Crystal Dunn', sex='female', dob='1991-01-30', dx='2026-07-13',
         records=[
             ('condition', '2026-07-13', 'Late latent syphilis', DR[1]),
             ('trep', '2026-07-13', 'reactive'),
             ('rpr', '2026-07-13', '1:2', {}),
             ('hcg', '2026-07-13', 'negative', {}),
             ('bpg', '2026-07-13', '2.4 million units IM', RN[2], 'R gluteal. 1/3.'),
             ('note', '2026-07-21', '0845', 'nurse', RN[2], 'Telephone encounter', 'No show 7/20 for Bicillin #2. VM left.'),
             ('note', '2026-07-28', '0845', 'nurse', RN[2], 'Telephone encounter', 'No show 7/27. Unable to reach.'),
             ('note', '2026-09-15', '1530', 'clinician', DR[1], 'Progress note',
              'Returns after missing injections. Reports LMP ~7 wks ago. Serum quantitative hCG sent. Will '
              'restart Bicillin series once hCG back; pt agrees to return.'),
             ('hcg', '2026-09-15', None, {'comment': 'In process.'}),
         ],
         facts=dict(stage='late_latent'),
         unknown=dict(code=PEND, kind='pending', best='not_pregnant', negative='not_pregnant',
                      options={'pregnant': dict(pregnant=True), 'not_pregnant': dict(pregnant=False)}),
         truth={ADQ: ('confirmed', None), PRG: ('cannot_determine', PEND)},
         kinds={ADQ: 'relevance', PRG: 'undeterminable'},
         gaps={'pending_hcg': (ADQ, PRG)}),

    # ---------------------------------------------------------------- 22: later local note gives the wrong
    # delivery date; the hospital record governs.
    dict(key='p22', name='Hannah Lowe', sex='female', dob='1996-06-06', dx='2025-09-08',
         records=[
             ('rpr', '2025-03-10', 'NR', {}),
             ('trep', '2025-09-08', 'reactive'),
             ('rpr', '2025-09-08', '1:8', {}),
             ('condition', '2025-09-08', 'Early latent syphilis', DR[3]),
             ('note', '2025-09-08', '1000', 'clinician', DR[3], 'Prenatal visit', '30w0d. RPR newly reactive (NR 3/10 at 4 wks). Early latent. Bicillin today.'),
             ('bpg', '2025-09-08', '2.4 million units IM', RN[3], 'L gluteal.'),
             ('outside', '2025-10-20', 'Riverside Hospital',
              'RIVERSIDE HOSPITAL - DISCHARGE SUMMARY (L&D)\nPatient: LOWE, HANNAH  DOB 06/06/1996\nAdmit 10/09/2025 '
              'in labor. Delivery: 10/10/2025 04:12, spontaneous vaginal delivery, live female infant 3050 g. Maternal '
              'RPR 1:4 at delivery; maternal treatment 09/08/2025 per outpatient records. Discharged 10/12/2025.'),
             ('note', '2025-11-20', '1100', 'clinician', DR[3], 'Postpartum visit',
              '6 wk postpartum visit. Delivered 10/7 at Riverside, uncomplicated. Breastfeeding. Mood good.'),
             ('rpr', '2026-03-12', '1:2', {}),
         ],
         facts=dict(stage='early_latent', pregnant=True, delivery='2025-10-10'),
         wrong={'latest_wins': dict(delivery='2025-10-07')},
         gaps={'outside_received': (PRG,)},
         kinds={PRG: 'nonissue'}),

    # ---------------------------------------------------------------- 23: series started, then restaged early
    # latent when outside negative arrived; stopped after two doses.
    dict(key='p23', name='Derek Vaughn', sex='male', dob='1985-03-11', dx='2025-12-01',
         records=[
             ('trep', '2025-12-01', 'reactive'),
             ('rpr', '2025-12-01', '1:4', {}),
             ('condition', '2025-12-01', 'Latent syphilis, unknown duration', DR[2]),
             ('bpg', '2025-12-01', '2.4 million units IM', RN[1], 'R gluteal. 1 of 3.'),
             ('bpg', '2025-12-08', '2.4 million units IM', RN[1], 'L gluteal. 2 of 3.'),
             ('outside', '2025-12-10', 'Lakeview Plasma Center',
              'LAKEVIEW PLASMA CENTER - DONOR TESTING\nDonor: VAUGHN, DEREK  DOB 03/11/1985\nCollected 08/04/2025: '
              'RPR NONREACTIVE. HBsAg neg. HIV neg.'),
             ('condition', '2025-12-11', 'Early latent syphilis', DR[2]),
             ('note', '2025-12-11', '0915', 'clinician', DR[2], 'Progress note',
              'Plasma center records received: RPR nonreactive 8/4/25, so infection acquired within the past '
              'year. Revising diagnosis from latent of unknown duration to early latent syphilis. Treatment is '
              'complete; cancel the remaining injection. Pt informed.'),
             ('rpr', '2026-06-03', '1:1', {}),
         ],
         facts=dict(stage='early_latent'),
         wrong={'structured_only': dict(stage='late_latent')},
         gaps={'outside_received': (ADQ,)},
         kinds={ADQ: 'nonissue'}),

    # ---------------------------------------------------------------- 24: pregnant, 10-day gap in a late latent series.
    dict(key='p24', name='Imani Jackson', sex='female', dob='1998-02-25', dx='2025-03-03',
         records=[
             ('note', '2025-03-03', '1000', 'clinician', DR[1], 'Prenatal visit',
              '18w3d, new to care. RPR 1:2, TP-PA +. No prior tests available; pt unsure of past testing. Latent '
              'syphilis, duration unknown. Bicillin weekly x3.'),
             ('trep', '2025-03-03', 'reactive'),
             ('rpr', '2025-03-03', '1:2', {}),
             ('condition', '2025-03-03', 'Late latent syphilis', DR[1]),
             ('bpg', '2025-03-03', '2.4 million units IM', RN[2], 'R gluteal.'),
             ('bpg', '2025-03-10', '2.4 million units IM', RN[2], 'L gluteal.'),
             ('note', '2025-03-17', '1600', 'nurse', RN[2], 'Telephone encounter', 'Pt no ride today, rescheduled to Monday 3/24.'),
             ('bpg', '2025-03-24', '2.4 million units IM', RN[2], 'R gluteal.'),
             ('note', '2025-03-24', '1130', 'clinician', DR[1], 'Prenatal visit', '21w3d. Third Bicillin today (a week late; no transport, then clinic closed Friday). Series complete.'),
             ('outside', '2025-08-06', 'Riverside Hospital',
              'RIVERSIDE HOSPITAL - DISCHARGE SUMMARY (L&D)\nPatient: JACKSON, IMANI  DOB 02/25/1998\nDelivery '
              '08/01/2025, repeat low transverse cesarean, live male infant 3310 g. Maternal RPR 1:1.'),
             ('rpr', '2025-09-10', '1:1', {}),
             ('rpr', '2026-03-09', 'NR', {}),
         ],
         facts=dict(stage='late_latent', pregnant=True, delivery='2025-08-01'),
         gaps={'outside_received': (PRG,)},
         truth={ADQ: ('confirmed', None), PRG: ('confirmed', None)}, kinds={ADQ: 'real', PRG: 'real'},
         requests={ADQ: 'Pharmacy QA: third Bicillin dose given 14 days after the second. Please review.'}),

    # ---------------------------------------------------------------- 25: primary, left before the injection.
    dict(key='p25', name='Tyrell Adams', sex='male', dob='2002-04-18', dx='2026-04-20',
         records=[
             ('outside', '2026-04-18', 'Eastside Community Health',
              'EASTSIDE COMMUNITY HEALTH - REFERRAL\nPt: Tyrell Adams DOB 4/18/2002. Painless penile ulcer x 1 wk, '
              'RPR 1:16. Please evaluate and treat for syphilis. - M. Reed, NP'),
             ('trep', '2026-04-20', 'reactive'),
             ('rpr', '2026-04-20', '1:16', {}),
             ('condition', '2026-04-20', 'Primary syphilis', DR[0]),
             ('note', '2026-04-20', '1500', 'clinician', DR[0], 'Progress note', 'Indurated painless chancre on shaft. Primary syphilis. Bicillin L-A ordered.'),
             ('med', '2026-04-20', 'Bicillin L-A 2.4 million units', '2.4 million units IM', RN[3], 'Pt left the clinic before the injection was given.', 'not-done'),
             ('note', '2026-04-22', '1000', 'nurse', RN[3], 'Outreach', 'Called x2, VM full. Text sent.'),
             ('note', '2026-05-06', '1000', 'nurse', RN[3], 'Outreach', 'DIS referral placed for untreated primary syphilis.'),
         ],
         facts=dict(stage='primary'),
         truth={ADQ: ('confirmed', None)}, kinds={ADQ: 'real'}),

    # ---------------------------------------------------------------- 26: doxycycline post-exposure prophylaxis
    # is not treatment.
    dict(key='p26', name='Julian Moreau', sex='male', dob='1988-12-02', dx='2026-02-09',
         records=[
             ('rpr', '2025-10-06', 'NR', {}),
             ('dispense', '2025-10-06', 'Doxycycline hyclate 100 mg tablet', 20, 30, 'Take 2 tablets (200 mg) once within 72 hours after condomless sex. Max 200 mg per 24 h.', 'doxy-PEP'),
             ('dispense', '2026-01-12', 'Doxycycline hyclate 100 mg tablet', 20, 30, 'Take 2 tablets (200 mg) once within 72 hours after condomless sex. Max 200 mg per 24 h.', 'doxy-PEP refill'),
             ('trep', '2026-02-09', 'reactive'),
             ('rpr', '2026-02-09', '1:32', {}),
             ('condition', '2026-02-09', 'Early latent syphilis', DR[3]),
             ('note', '2026-02-09', '1245', 'clinician', DR[3], 'Progress note',
              'Routine PrEP/doxy-PEP visit. RPR 1:32 (NR 10/2025), TP-PA +. Asymptomatic, no lesions. Uses doxy-PEP '
              '~2x/week, so has had a lot of doxycycline recently; likely already partially treated. Will hold off '
              'on Bicillin and recheck RPR in 3 months.'),
             ('rpr', '2026-05-11', '1:16', {}),
         ],
         facts=dict(stage='early_latent', doses=[('2025-10-06', 'pep'), ('2026-01-12', 'pep')]),
         wrong={'pep_is_treatment': dict(doses=[('2026-02-09', 'bpg')])},
         truth={ADQ: ('confirmed', None)}, kinds={ADQ: 'inference'}),

    # ---------------------------------------------------------------- controls
    dict(key='p27', name='Kevin Lindqvist', sex='male', dob='1976-07-15', dx='2025-05-12',
         records=[
             ('rpr', '2024-11-04', 'NR', {}),
             ('trep', '2025-05-12', 'reactive'),
             ('rpr', '2025-05-12', '1:8', {}),
             ('condition', '2025-05-12', 'Early latent syphilis', DR[0]),
             ('bpg', '2025-05-12', '2.4 million units IM', RN[0], 'R gluteal.'),
             ('rpr', '2025-11-14', '1:2', {}),
             ('rpr', '2026-05-18', '1:1', {}),
         ],
         facts=dict(stage='early_latent'), kinds={}),
    dict(key='p28', name='Peter Osei', sex='male', dob='1962-02-03', dx='2024-09-09',
         records=[
             ('condition', '2024-09-09', 'Late latent syphilis', DR[1]),
             ('trep', '2024-09-09', 'reactive'),
             ('rpr', '2024-09-09', '1:4', {}),
             ('bpg', '2024-09-09', '2.4 million units IM', RN[1], 'R gluteal.'),
             ('bpg', '2024-09-16', '2.4 million units IM', RN[1], 'L gluteal.'),
             ('bpg', '2024-09-24', '2.4 million units IM', RN[1], 'R gluteal.'),
             ('rpr', '2025-03-11', '1:2', {}),
             ('rpr', '2025-09-15', '1:2', {}),
         ],
         facts=dict(stage='late_latent'), kinds={}),
    dict(key='p29', name='Rachel Kim', sex='female', dob='1995-10-28', dx='2025-06-02',
         records=[
             ('rpr', '2025-01-20', 'NR', {}),
             ('note', '2025-06-02', '1000', 'clinician', DR[2], 'Prenatal visit', '20w0d. RPR newly reactive (NR at 6 wks). Early latent syphilis. Bicillin today.'),
             ('trep', '2025-06-02', 'reactive'),
             ('rpr', '2025-06-02', '1:8', {}),
             ('condition', '2025-06-02', 'Early latent syphilis', DR[2]),
             ('bpg', '2025-06-02', '2.4 million units IM', RN[3], 'R gluteal.'),
             ('outside', '2025-10-20', 'Riverside Hospital',
              'RIVERSIDE HOSPITAL - DISCHARGE SUMMARY (L&D)\nPatient: KIM, RACHEL  DOB 10/28/1995\nDelivery 10/15/2025, '
              'SVD, live female infant 3200 g. Maternal RPR 1:2.'),
             ('rpr', '2025-12-05', '1:2', {}),
             ('rpr', '2026-06-01', '1:1', {}),
         ],
         facts=dict(stage='early_latent', pregnant=True, delivery='2025-10-15'), kinds={},
         gaps={'outside_received': (PRG,)}),
]

# Routine, decision-irrelevant charting so case records do not stand out.
ROUTINE = {
    'p03': [('lab', '2025-09-15', 'Chlamydia/Gonorrhea NAAT', 'Not detected')],
    'p04': [routine('2025-06-02', RN[0], 'BP 142/88, HR 76. Pt reports adherence to lisinopril.')],
    'p08': [('lab', '2026-01-20', 'HIV-1/2 Ag/Ab', 'Nonreactive')],
    'p10': [('lab', '2025-02-24', 'HIV-1/2 Ag/Ab', 'Nonreactive'), ('lab', '2025-02-24', 'Chlamydia/Gonorrhea NAAT', 'Not detected')],
    'p12': [('lab', '2024-05-06', 'HIV-1/2 Ag/Ab', 'Nonreactive')],
    'p14': [routine('2026-06-16', RN[3], 'Portal message: pt asked for copy of vaccine record; mailed.')],
    'p16': [routine('2025-11-03', RN[1], 'Flu vaccine given L deltoid. BP 130/80.')],
    'p19': [('lab', '2026-01-05', 'Hepatitis B surface antigen', 'Negative')],
    'p25': [('lab', '2026-04-20', 'HIV-1/2 Ag/Ab', 'Nonreactive')],
    'p26': [('lab', '2026-02-09', 'Chlamydia/Gonorrhea NAAT', 'Not detected'), ('lab', '2026-02-09', 'HIV-1 RNA (PrEP)', 'Not detected')],
    'p27': [('lab', '2025-05-12', 'HIV-1/2 Ag/Ab', 'Nonreactive'),
            routine('2025-11-14', RN[0], 'Here for 6-mo RPR. No new concerns.')],
    'p28': [routine('2025-03-11', RN[1], 'Here for 6-mo RPR. BP 128/82.')],
}
for p in PATIENTS:
    p['records'] = p['records'] + ROUTINE.get(p['key'], [])
    for kind, name in (('truth', {}), ('kinds', {}), ('requests', {}), ('gaps', {}), ('wrong', {})):
        p.setdefault(kind, name)
