from superpyrate.tasks import produce_valid_csv_file
import os
import tempfile
import csv
from pytest import fixture

from pyrate.algorithms.aisparser import readcsv, parse_raw_row, \
                                        AIS_CSV_COLUMNS, \
                                        validate_row
import logging
LOGGER = logging.getLogger(__name__)

logging.basicConfig(filename='tests.log',
                    level=logging.DEBUG,
                    filemode='w',
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    datefmt='%m/%d/%Y %I:%M:%S %p')

class TestUnicodeError:
    """Given fault, bugridden, error prone files, test that ingest still happens
    """

    def test_unicode_error_in_csv(self, set_tmpdir_environment):
        unicode_error_file = "tests/fixtures/unicode_error.csv"
        actual_output = os.path.join(str(set_tmpdir_environment), 'actual_output.csv')
        produce_valid_csv_file(unicode_error_file, actual_output)

        expected = ['431602153','2013-02-08 12:59:19','1','0','23.1','133.427716667','32.6470833333','54.0','50.0','','','','','','','','']
        with open(actual_output, 'r') as actual_file:
            actual_file.readline()
            for actual in actual_file:
                assert actual.rstrip('\r\n') == ",".join(expected)

    def test_unicode_error_in_multiline_csv(self, set_tmpdir_environment):
        ml_unicode_error_file = "tests/fixtures/unicode_error_multiline.csv"
        actual_output = os.path.join(str(set_tmpdir_environment), 'actual_output.csv')
        produce_valid_csv_file(ml_unicode_error_file, actual_output)

        expected = [['431602153','2013-02-08 12:59:19','1','0','23.1','133.427716667','32.6470833333','54.0','50.0','','','','','','','',''],
                    ['431602353','2013-02-08 12:59:19','1','0','23.1','133.427716667','32.6470833333','54.0','50.0','','','','','','','',''],
                    ['121602153','2013-02-08 12:59:19','1','0','23.1','133.427716667','32.6470833333','54.0','50.0','','','','','','','',''],
                    ['432302153','2013-02-08 12:59:19','1','0','23.1','133.427716667','32.6470833333','54.0','50.0','','','','','','','',''],
                    ['431623453','2013-02-08 12:59:19','1','0','23.1','133.427716667','32.6470833333','54.0','50.0','','','','','','','',''],
                    ['431602443','2013-02-08 12:59:19','1','0','23.1','133.427716667','32.6470833333','54.0','50.0','','','','','','','',''],
                    ['431123153','2013-02-08 12:59:19','1','0','23.1','133.427716667','32.6470833333','54.0','50.0','','','','','','','',''],
                    ['439239823','2013-02-08 12:59:19','1','0','23.1','133.427716667','32.6470833333','54.0','50.0','','','','','','','',''],
                    ['431234123','2013-02-08 12:59:19','1','0','23.1','133.427716667','32.6470833333','54.0','50.0','','','','','','','',''],
                    ['431092573','2013-02-08 12:59:19','1','0','23.1','133.427716667','32.6470833333','54.0','50.0','','','','','','','','']]
        with open(actual_output, 'r') as actual_file:
            actual_file.readline()
            for actual, expected in zip(actual_file, expected):
                assert actual.rstrip('\n\r') == ",".join(expected)


class TestGenerationOfValidCsv():
    """
    """

    def test_script_runs(self, set_tmpdir_environment):
        """
        """
        input_file = "tests/fixtures/simple.csv"
        output_file = os.path.join(str(set_tmpdir_environment), 'test_output.csv')
        produce_valid_csv_file(input_file, output_file)

    def test_valid_files_produced(self, set_tmpdir_environment):
        """ Once we have the files, check that some generated test files are
        correctly ingested, including csv files where commas appear in fields
        (e.g. in vessel names)
        """
        e_input_file = 'tests/fixtures/error.csv'
        e_output_file = os.path.join(str(set_tmpdir_environment), 'test_output.csv')
        produce_valid_csv_file(e_input_file, e_output_file)

        expected = "355999000,2013-07-15 08:18:57,5,,,,,,,8514083,68.0,JP MKW,PYXIS,7,31,0,0"
        with open(e_output_file, 'r') as actual_file:
            assert actual_file.readline().rstrip('\n\r').split(',') == AIS_CSV_COLUMNS
            assert actual_file.readline().rstrip('\n\r') == expected

    def test_clean_files_produced(self):
        """ Check that valid data goes into a clean folder
        """
        pass

    def test_dirty_files_produced(self):
        """ Check that data which doesn't pass validation goes into a dirty
        folder
        """
        pass

    def test_invalid_data_triggers_log_entry(self):
        """ Rows which are invalid, i.e. cannot be read, should trigger an
        entry in the logfile
        """
        pass