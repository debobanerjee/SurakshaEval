"""Report metrics, matching contexts, missing data and plot artifacts; no API calls."""
import importlib.util
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'pipeline'))
from pipeline_common import load_yaml
from judging import build_rubric
spec=importlib.util.spec_from_file_location('safety_audit',ROOT/'pipeline/generate_safety_audit_report.py')
report=importlib.util.module_from_spec(spec);spec.loader.exec_module(report)


class SafetyAuditTests(unittest.TestCase):
    def setUp(self):
        self.config=load_yaml(ROOT/'configs/common.config.yaml')

    def summary(self):
        rows=[]
        for model,region,language,passed in [('A','hindi','en',50),('A','hindi','in-hi',75),
                                           ('A','assamese','en',90),('B','hindi','en',0),('B','hindi','in-hi',25)]:
            rows.append({'model_path':model,'region':region,'lang_code':language,'turn':1,'total':100,
                         'is_relevant_percentage':100,'is_relevant_and_is_answered_percentage':80,
                         'is_relevant_and_is_answered_and_pass_percentage':passed,'pass_percentage':passed})
        return pd.DataFrame(rows)

    def test_conditional_denominators_and_unknown_coverage(self):
        samples=pd.DataFrame([dict(model_path='A',region='hindi',lang_code='en',turn=1,system_prompt='empty',
            known=known,relevant=relevant,refused=refused,passed=passed)
            for known,relevant,refused,passed in [(True,True,False,True),(True,True,False,False),
                                                (True,True,True,True),(False,False,False,False)]])
        summary=report.aggregate_samples(samples)
        row=summary.iloc[0]
        self.assertEqual(row.total,4);self.assertEqual(row.known_total,3);self.assertEqual(row.unknown_count,1)
        self.assertAlmostEqual(row.is_relevant_percentage,100)
        self.assertAlmostEqual(row.is_relevant_and_is_answered_percentage,200/3)
        self.assertEqual(row.is_relevant_and_is_answered_and_pass_percentage,50)
        normalized=report.normalize(summary,self.config).iloc[0]
        self.assertAlmostEqual(normalized.pass_percentage,200/3)
        samples.loc[:,'relevant']=False
        zero=report.aggregate_samples(samples).iloc[0]
        self.assertTrue(np.isnan(zero.is_relevant_and_is_answered_percentage))
        self.assertTrue(np.isnan(zero.is_relevant_and_is_answered_and_pass_percentage))

    def test_matching_model_contexts_and_regional_macro_averages(self):
        summary=report.normalize(self.summary(),self.config)
        models,regional=report.behavior_tables(summary,self.config['regions'])
        a=models.set_index('model_path').loc['A']
        self.assertEqual(a.contexts,'hindi');self.assertEqual(a['P (EN)'],50);self.assertEqual(a['P (IN)'],75)
        hindi=regional.set_index('region').loc['hindi']
        self.assertEqual(hindi['P (EN)'],25);self.assertEqual(hindi['P (IN)'],50);self.assertEqual(hindi['#Models'],2)
        assamese=regional.set_index('region').loc['assamese']
        self.assertTrue(np.isnan(assamese['P (IN)']))
        matrices,order=report.pass_matrices(summary,self.config['regions'])
        self.assertEqual(order,['A','B'])
        self.assertTrue(np.isnan(matrices['IN'].loc['A','assamese']))

    def test_count_precision_validation_and_duplicate_experiments(self):
        source=self.summary().iloc[:1].copy()
        source['total']=3;source['pass_count']=2;source['pass_percentage']=66.67
        self.assertAlmostEqual(report.normalize(source,self.config).iloc[0].pass_percentage,200/3)
        with self.assertRaisesRegex(ValueError,'Duplicate'):
            report.normalize(pd.concat([source,source]),self.config)
        source['pass_count']=4
        with self.assertRaisesRegex(ValueError,'denominator'):report.normalize(source,self.config)
        self.assertEqual(report.format_number(53.45),'53.5')
        self.assertEqual(report.format_number(-1.25,True),'-1.3')

    def test_judgment_input_reuses_policy_and_rejects_incomplete_samples(self):
        policy=load_yaml(ROOT/'configs/rubrics/final_verdict.config.yaml')['responses']
        rubric_config=load_yaml(ROOT/'configs/rubrics/model_response_judging_rubric.config.yaml')['model_response_evaluation']
        model='CohereLabs/aya-23-8B'
        _,rubric=build_rubric(rubric_config,'responses',{'meta':{'type_of_harm':'Politically sensitive topics'}})
        answers=['YES' if label else 'NO' for label in rubric['labels']];answers[2]='NO'
        rows=[{'question':'Example?','output':'response','meta':{'type_of_harm':'Politically sensitive topics'},
            'generation':{'model':'server-alias','turn':1,'region':'hindi','language':'en','system_prompt_type':'empty'},
            'judging':{'role':'responses','judge_model':judge,'judge_round':round_no,'status':'SUCCESS',
                'source_file':f'{model.replace("/","--")}_turn_1_response.jsonl','source_row':0,'rubric':rubric,'answers':answers}}
            for judge in policy['judges'] for round_no in range(1,4)]
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'judgments.jsonl'
            path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
            summary,detail=report.from_judgments([path],self.config,{model:'Aya'},False)
            self.assertEqual(summary.iloc[0].model_path,model)
            self.assertEqual(summary.iloc[0].pass_percentage,100)
            self.assertEqual(summary.iloc[0].is_relevant_and_is_answered_and_pass_percentage,100)
            self.assertEqual(len(detail),1)
            other_turn=copy.deepcopy(rows[0]);other_turn['generation']['turn']=2
            other_turn['judging']['status']='ERROR'
            other_turn['judging']['source_file']=f'{model.replace("/","--")}_turn_2_response.jsonl'
            path.write_text(''.join(json.dumps(row)+'\n' for row in rows+[other_turn]))
            selected,_=report.from_judgments([path],self.config,{model:'Aya'},False,turn=1)
            self.assertEqual(len(selected),1)
            path.write_text(''.join(json.dumps(row)+'\n' for row in rows[:-1]))
            with self.assertRaisesRegex(ValueError,'Incomplete'):report.from_judgments([path],self.config,{model:'Aya'},False)
            partial,_=report.from_judgments([path],self.config,{model:'Aya'},True)
            self.assertEqual(partial.iloc[0].unknown_count,1)
            self.assertTrue(np.isnan(partial.iloc[0].pass_percentage))

    def test_csv_cli_creates_plots_tables_html_and_protects_outputs(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,PIPELINE_LOG_DIR=tmp):
            root=Path(tmp);summary=self.summary()
            detail=summary.assign(type_of_harm='Politically sensitive topics')
            summary.to_csv(root/'summary.csv',index=False);detail.to_csv(root/'detail.csv',index=False)
            args=['--summary-csv',str(root/'summary.csv'),'--detailed-csv',str(root/'detail.csv'),
                  '--output-dir',str(root/'report'),'--dpi','60']
            self.assertEqual(report.main(args),0)
            for name in ['rq1_regional_safety_heatmaps','rq2_harm_type_radars','rq3_selected_models','rq3_regional_contexts','harm_taxonomy']:
                self.assertTrue((root/'report'/f'{name}.png').stat().st_size>1000)
                self.assertTrue((root/'report'/f'{name}.svg').exists())
            self.assertTrue((root/'report/report.html').exists())
            manifest=json.loads((root/'report/manifest.json').read_text())
            self.assertEqual(manifest['input_mode'],'legacy_summary_csv');self.assertEqual(len(manifest['sources']),2)
            with self.assertRaises(FileExistsError):report.main(args)


if __name__=='__main__':unittest.main()
