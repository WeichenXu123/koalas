#
# Copyright (C) 2019 Databricks, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import os
import shutil
import tempfile
from contextlib import contextmanager

import pandas as pd
import numpy as np

from databricks import koalas as ks
from databricks.koalas.testing.utils import ReusedSQLTestCase, TestUtils


def normalize_text(s):
    return '\n'.join(map(str.strip, s.strip().split('\n')))


class CsvTest(ReusedSQLTestCase, TestUtils):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix=CsvTest.__name__)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    @property
    def csv_text(self):
        return normalize_text(
            """
            name,amount
            Alice,100
            Bob,-200
            Charlie,300
            Dennis,400
            Edith,-500
            Frank,600
            Alice,200
            Frank,-200
            Bob,600
            Alice,400
            Frank,200
            Alice,300
            Edith,600
            """)

    @property
    def csv_text_2(self):
        return normalize_text(
            """
            A,B
            item1,1
            item2,1,2
            item3,1,2,3,4
            item4,1
            """)

    @property
    def csv_text_with_comments(self):
        return normalize_text(
            """
            # header
            %s
            # comment
            Alice,400
            Edith,600
            # footer
            """ % self.csv_text)

    @contextmanager
    def csv_file(self, csv):
        with self.temp_file() as tmp:
            with open(tmp, 'w') as f:
                f.write(csv)
            yield tmp

    def test_read_csv(self):
        with self.csv_file(self.csv_text) as fn:

            def check(header='infer', names=None, usecols=None):
                expected = pd.read_csv(fn, header=header, names=names, usecols=usecols)
                actual = ks.read_csv(fn, header=header, names=names, usecols=usecols)
                self.assertPandasAlmostEqual(expected, actual.toPandas())

            check()
            check(header=None)
            check(header=0)
            check(names=['n', 'a'])
            check(header=0, names=['n', 'a'])
            check(usecols=[1])
            check(usecols=[1, 0])
            check(usecols=['amount'])
            check(usecols=['amount', 'name'])
            check(usecols=[])
            check(usecols=[1, 1])
            check(usecols=['amount', 'amount'])
            check(names=['n', 'a'], usecols=['a'])

            # check with pyspark patch.
            expected = pd.read_csv(fn)
            actual = ks.read_csv(fn)
            self.assertPandasAlmostEqual(expected, actual.toPandas())

            self.assertRaisesRegex(ValueError, 'non-unique',
                                   lambda: ks.read_csv(fn, names=['n', 'n']))
            self.assertRaisesRegex(ValueError, 'does not match the number.*3',
                                   lambda: ks.read_csv(fn, names=['n', 'a', 'b']))
            self.assertRaisesRegex(ValueError, 'does not match the number.*3',
                                   lambda: ks.read_csv(fn, header=0, names=['n', 'a', 'b']))
            self.assertRaisesRegex(ValueError, 'Usecols do not match.*3',
                                   lambda: ks.read_csv(fn, usecols=[1, 3]))
            self.assertRaisesRegex(ValueError, 'Usecols do not match.*col',
                                   lambda: ks.read_csv(fn, usecols=['amount', 'col']))
            self.assertRaisesRegex(ValueError, 'Unknown header argument 1',
                                   lambda: ks.read_csv(fn, header='1'))
            expected_error_message = ("'usecols' must either be list-like of all strings, "
                                      "all unicode, all integers or a callable.")
            self.assertRaisesRegex(ValueError, expected_error_message,
                                   lambda: ks.read_csv(fn, usecols=[1, 'amount']))

    def test_read_with_spark_schema(self):
        with self.csv_file(self.csv_text_2) as fn:
            actual = ks.read_csv(fn, names="A string, B string, C long, D long, E long")
            expected = pd.read_csv(fn, names=['A', 'B', 'C', 'D', 'E'])
            self.assertEqual(repr(expected), repr(actual))

    def test_read_csv_with_comment(self):
        with self.csv_file(self.csv_text_with_comments) as fn:
            expected = pd.read_csv(fn, comment='#')
            actual = ks.read_csv(fn, comment='#')
            self.assertPandasAlmostEqual(expected, actual.toPandas())

            self.assertRaisesRegex(ValueError, 'Only length-1 comment characters supported',
                                   lambda: ks.read_csv(fn, comment='').show())
            self.assertRaisesRegex(ValueError, 'Only length-1 comment characters supported',
                                   lambda: ks.read_csv(fn, comment='##').show())
            self.assertRaisesRegex(ValueError, 'Only length-1 comment characters supported',
                                   lambda: ks.read_csv(fn, comment=1))
            self.assertRaisesRegex(ValueError, 'Only length-1 comment characters supported',
                                   lambda: ks.read_csv(fn, comment=[1]))

    def test_read_csv_with_mangle_dupe_cols(self):
        self.assertRaisesRegex(ValueError, 'mangle_dupe_cols',
                               lambda: ks.read_csv('path', mangle_dupe_cols=False))

    def test_read_csv_with_parse_dates(self):
        self.assertRaisesRegex(ValueError, 'parse_dates',
                               lambda: ks.read_csv('path', parse_dates=True))

    def test_to_csv(self):
        pdf = pd.DataFrame({'a': [1, 2, 3], 'b': [4, 5, 6]}, index=[0, 1, 3])
        kdf = ks.DataFrame(pdf)

        self.assert_eq(kdf.to_csv(), pdf.to_csv(index=False))

        pdf = pd.DataFrame({
            'a': [1, np.nan, 3],
            'b': ["one", "two", None],
        }, index=[0, 1, 3])

        kdf = ks.from_pandas(pdf)

        self.assert_eq(kdf.to_csv(na_rep='null'), pdf.to_csv(na_rep='null', index=False))

        pdf = pd.DataFrame({
            'a': [1.0, 2.0, 3.0],
            'b': [4.0, 5.0, 6.0],
        }, index=[0, 1, 3])

        kdf = ks.from_pandas(pdf)

        self.assert_eq(kdf.to_csv(), pdf.to_csv(index=False))
        self.assert_eq(kdf.to_csv(header=False), pdf.to_csv(header=False, index=False))
        self.assert_eq(kdf.to_csv(), pdf.to_csv(index=False))

    def test_to_csv_with_path(self):
        pdf = pd.DataFrame({'a': [1, 2, 3], 'b': ['a', 'b', 'c']})
        kdf = ks.DataFrame(pdf)

        kdf.to_csv(self.tmp_dir, num_files=1)
        expected = pdf.to_csv(index=False)

        output_paths = [path for path in os.listdir(self.tmp_dir) if path.startswith("part-")]
        assert len(output_paths) > 0
        output_path = "%s/%s" % (self.tmp_dir, output_paths[0])
        self.assertEqual(open(output_path).read(), expected)

    def test_to_csv_with_path_and_basic_options(self):
        pdf = pd.DataFrame({'a': [1, 2, 3], 'b': ['a', 'b', 'c']})
        kdf = ks.DataFrame(pdf)

        kdf.to_csv(self.tmp_dir, num_files=1, sep='|', header=False)
        expected = pdf.to_csv(index=False, sep='|', header=False)

        output_paths = [path for path in os.listdir(self.tmp_dir) if path.startswith("part-")]
        assert len(output_paths) > 0
        output_path = "%s/%s" % (self.tmp_dir, output_paths[0])
        self.assertEqual(open(output_path).read(), expected)

    def test_to_csv_with_path_and_pyspark_options(self):
        pdf = pd.DataFrame({'a': [1, 2, 3, None], 'b': ['a', 'b', 'c', None]})
        kdf = ks.DataFrame(pdf)

        kdf.to_csv(self.tmp_dir, nullValue="null", num_files=1)
        expected = pdf.to_csv(index=False, na_rep='null')

        output_paths = [path for path in os.listdir(self.tmp_dir) if path.startswith("part-")]
        assert len(output_paths) > 0
        output_path = "%s/%s" % (self.tmp_dir, output_paths[0])
        self.assertEqual(open(output_path).read(), expected)
