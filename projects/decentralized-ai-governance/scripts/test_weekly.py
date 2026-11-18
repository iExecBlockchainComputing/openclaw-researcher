import copy
import json
from pathlib import Path
import tempfile
import unittest
from weekly import prepare, validate

class WeeklyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.p = Path(self.temp.name)
        (self.p/'corpus').mkdir()
        (self.p/'note.md').write_text('Evidence')
        (self.p/'draft.md').write_text('Digest')
        (self.p/'weekly-config.json').write_text(json.dumps({'max_new_full_reads':1,'max_digest_papers':1}))
        self.r={'record_id':'a','notes':['note.md'],'versions':[{'arxiv_id':'av1','reading_status':'critical_reading_completed','reading_coverage':{'note':'note.md'}}]}
        (self.p/'corpus/references.jsonl').write_text(json.dumps(self.r)+'\n')
        self.packet=prepare(self.p)
        self.d={'assessments':[{'record_id':'a','decision':'read','reason':'relevant'}], 'selected':[{'record_id':'a','version':'av1','note':'note.md','reason':'evidence'}],'draft':'draft.md'}
    def test_valid_draft_is_not_delivery(self):
        self.assertEqual(validate(self.p,self.packet,self.d)['status'],'draft_validated_not_sent')
    def test_missing_assessment_blocks(self):
        self.d['assessments']=[]
        with self.assertRaises(ValueError): validate(self.p,self.packet,self.d)
    def test_unread_version_blocks(self):
        self.d['selected'][0]['version']='av2'
        with self.assertRaises(ValueError): validate(self.p,self.packet,self.d)
    def test_budget_blocks(self):
        self.packet['config']['max_new_full_reads']=0
        with self.assertRaises(ValueError): validate(self.p,self.packet,self.d)
    def test_duplicate_selection_blocks(self):
        self.d['selected']*=2
        with self.assertRaises(ValueError): validate(self.p,self.packet,self.d)
    def test_snapshot_preserves_registry(self):
        before=(self.p/'corpus/references.jsonl').read_bytes()
        prepare(self.p)
        self.assertEqual(before,(self.p/'corpus/references.jsonl').read_bytes())
if __name__=='__main__': unittest.main()
