import asyncio,json,sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'windows'))
from quality_checks import numbers,quality_flags

class NumericTranslationTests(unittest.TestCase):
    def test_equivalent_spoken_and_written_quantities(self):
        for source,target in [('Wait one hundred twenty-five seconds.','請等125秒。'),('There are two thousand and five people.','有2005人。'),('The total is 1,250.50.','總數是1250.5。'),('Wait twenty-one seconds.','等21秒。')]:
            self.assertNotIn('number_mismatch',quality_flags(source,target,'en'))

    def test_distinct_numbers_are_not_added_or_hidden(self):
        self.assertEqual(numbers('one and two'),numbers('1 and 2'))
        self.assertNotEqual(numbers('one hundred and two and three'),numbers('105'))
        self.assertNotEqual(numbers('one hundred five six'),numbers('111'))
        self.assertIn('number_mismatch',quality_flags('We need one hundred points.','需要10分。','en'))
        self.assertNotEqual(numbers('one hundred and five'),numbers('one hundred and fifty'))
        self.assertIn('number_mismatch',quality_flags('The price is 1,200.','價格是12。','en'))

    def test_chinese_large_units_and_mixed_digits(self):
        for source,target in [('Ten thousand people came.','來了一萬人。'),('It sold 125,000 copies.','賣出12萬5千份。'),('The budget is 350 million.','預算是3.5億。'),('The budget is 350 million.','預算是3億5000萬。'),('Twelve million viewers.','1,200萬名觀眾。'),('Twelve hundred people.','1200人。'),('A hundred points.','100分。'),('Two thousand five hundred dollars.','兩千五百元。'),('Revenue hit 1.5 billion.','營收達15億。')]:
            self.assertNotIn('number_mismatch',quality_flags(source,target,'en'),(source,target))
        self.assertIn('number_mismatch',quality_flags('Ten thousand people came.','來了一千人。','en'))
        self.assertIn('number_mismatch',quality_flags('It sold 125,000 copies.','賣出12萬份。','en'))

    def test_chinese_words_with_unit_characters_stay_text(self):
        for text in ['千萬不要放棄','萬一他來了','我們一起走','十全十美']:
            self.assertEqual(numbers(text),numbers(''),text)

class RealBenchmarkNumberCases(unittest.TestCase):
    """Cases from the 2026-10-24 FLEURS level-normalized run (ASR text, model translation)."""
    def test_correct_translations_are_not_flagged(self):
        for source,target in [
            ("One bomb exploded outside the Governor General's office.",'總督府外爆炸了一枚炸彈。'),
            ('Six hostages including the children elderly were released early','六名人質，包括兒童和長者，早前已獲釋'),
            ('The two compounds react with one another to form crystals','這兩種化合物反應會形成晶體'),
            ('US Corps of Engineers estimated that six inches of rainfall could breach','美國工程兵估計六英寸的雨量可能會突破'),
            ('for the spring box had ended a five-match losing streak.','春季賽季盒子已結束五連敗。'),
            ('is one of the main attractions of South Africa','是南非的主要景點之一'),
            ('so resist the temptation to remove even just one specimen.','所以請抵制移除任何一株植物的誘惑。'),
            ('As light pollution in their heyday was not the kind of problem it is today','由於他們繁榮時期的光汙染並不像現在這樣是一個問題'),
            ('Built by the Egyptians in the 3rd century BCE, the Great Pyramid is one of many','於前3世紀由埃及人建造的大金字塔是許多金字塔之一'),
            ('Construction was completed in August 2011.','施工完成於2011年8月。'),
            ('It will make getting about considerably easier.','這將使得出行變得十分容易。'),
            ('Wait ten minutes.','等十分鐘。'),('You may leave in March.','你可以在三月離開。')]:
            self.assertNotIn('number_mismatch',quality_flags(source,target,'en'),(source,target))

    def test_real_number_errors_are_still_flagged(self):
        for source,target in [('Six hostages were released.','五名人質獲釋。'),('One bomb exploded.','兩枚炸彈爆炸了。'),
                              ('The bridge is 15 meters high.','橋高5公尺。'),('The quake did not reach magnitude 6.5.','地震沒有達到6級。'),
                              ('Wait two weeks.','等三週。'),('It opened in March 2017.','它在2011年3月開放。'),
                              ('Completed in August 2011.','於2011年9月完工。'),('Wait ten minutes.','等十五分鐘。')]:
            self.assertIn('number_mismatch',quality_flags(source,target,'en'),(source,target))

    def test_measure_words_that_are_not_counts_stay_text(self):
        for text in ['四周很安靜','日本','全部','各位']:self.assertEqual(numbers(text),numbers(''),text)

async def numeric_translation_probe(guard=None):
    import httpx,numpy as np,models as m
    from live_audio import LiveSession
    state=LiveSession(vad=lambda frame:1.);calls=[]
    async def translate(*args):
        calls.append(1);await asyncio.sleep(.02);yield '請等125秒。'
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=m.app),base_url='http://127.0.0.1:8790') as client:
        with patch.object(m,'ready',True),patch.object(m,'gate',asyncio.Lock()),patch.object(m,'nmt_gate',asyncio.Lock()),patch.object(m,'sessions',{'numeric-regression':state}),patch.object(m,'quality_flags',guard or m.quality_flags),patch.object(m,'live_recognize',lambda *a:dict(text='Wait one hundred twenty-five seconds.',language='en',language_probability=.99)),patch.object(m,'tokens',translate):
            response=await client.post('/live/frame',content=(np.ones(8192)*10000).astype('<i2').tobytes(),headers={'X-Mosa-Session':'numeric-regression','X-Mosa-Flush':'1'})
    final=next(e for e in map(json.loads,response.text.splitlines()) if e['type']=='final')
    return final,len(calls)

class NumericRepairTests(unittest.IsolatedAsyncioTestCase):
    async def test_correct_translation_needs_only_one_inference(self):
        final,calls=await numeric_translation_probe()
        self.assertEqual(final['translation'],'請等125秒。')
        self.assertEqual(calls,1)
        self.assertNotIn('number_mismatch',final['quality_flags'])

if __name__=='__main__':unittest.main()
