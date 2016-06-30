""" Runs an integrated pipeline from raw zip file to database tables.  This mega-pipeline is constructed
out of three sub-pipelines.

1. Unzip individual AIS archives and output the csv files
2. Validate each of the csv files, processing using a derived version of the pyrate code,
   outputting vaidated csv files
3. Using the postgres `copy` command, ingest the data directly into the database

Entry points:
 - ProcessZipArchives(folder_of_zips, shell_script, with_db)

"""
import luigi
from luigi.contrib.external_program import ExternalProgramTask
from luigi.postgres import CopyToTable, PostgresQuery
from luigi import six
from luigi.util import requires
from superpyrate.tasks import produce_valid_csv_file
from pyrate.repositories.aisdb import AISdb
import csv
import psycopg2
import logging
import os
LOGGER = logging.getLogger('luigi-interface')


def get_working_folder(folder_of_zips=None):
    """

    Arguments
    =========
    folder_of_zips : str
        The absolute path of the folder of zips e.g. /home/user/Scratch/aiszip/2013/

    Returns
    =======
    working_folder : str
        The path of the working folder.  This is either set by the environment
        variable LUIGIWORK, or if empty is computed from the arguments
    """
    environment_variable = os.environ['LUIGIWORK']
    if environment_variable:
        working_folder = environment_variable
    else:
        if folder_of_zips is None:
            raise RuntimeError("No working folder defined")
        else:
            working_folder = os.path.dirname(os.path.dirname(folder_of_zips))
    return working_folder


class GetZipArchive(luigi.ExternalTask):
    """Returns a zipped archive as a LocalTarget
    """
    zip_file = luigi.Parameter(description='The file path of the archive to unzip')

    def output(self):
        return luigi.file.LocalTarget(self.zip_file)


class GetFolderOfArchives(luigi.ExternalTask):
    """Returns the folder of zipped archives as a LocalTarget
    """
    folder_of_zips = luigi.Parameter()

    def output(self):
        return luigi.file.LocalTarget(self.folder_of_zips)


class UnzippedArchive(ExternalProgramTask):
    """Unzips the zipped archive into a folder of AIS csv format files the same
    name as the original file

    Arguments
    =========
    zip_file : str
        The absolute path of the zipped archives

    Returns
    =======
    Outputs the files into a folder of the same name as the zip file in a
    subdirectory called 'unzipped'
    """
    zip_file = luigi.Parameter(description='The file path of the archive to unzip')
    shell_script = luigi.Parameter(default='../superpyrate/unzip_csvs.sh', significant=False)

    def requires(self):
        return GetZipArchive(self.zip_file)

    def program_args(self):
        # Removes the file extension to give a folder name as the output target
        output_folder = self.output().fn
        LOGGER.info('Running {0}, with args {1}, & {2}'.format(self.shell_script,
                                                               self.input().fn,
                                                               output_folder))
        return [self.shell_script, self.input().fn, output_folder]

    def output(self):
        out_root_dir = os.path.splitext(self.input().fn)[0]
        _, out_folder_name = os.path.split(out_root_dir)
        rootdir = get_working_folder()
        output_folder = os.path.join(rootdir,'files', 'unzipped', out_folder_name)
        # LOGGER.debug("Unzipped {}".format(output_folder))
        return luigi.file.LocalTarget(output_folder)


class ProcessCsv(luigi.Task):
    """
    """
    zip_file = luigi.Parameter()
    shell_script = luigi.Parameter(default='../superpyrate/unzip_csvs.sh', significant=False)

    def requires(self):
        return UnzippedArchive(self.zip_file, self.shell_script)

    def run(self):
        list_of_csvpaths = []
        LOGGER.debug("Processing csvs from {}".format(self.input().fn))
        for csvfile in os.listdir(self.input().fn):
            if os.path.splitext(csvfile)[1] == '.csv':
                list_of_csvpaths.append(os.path.join(self.input().fn, csvfile))

        yield [ValidMessages(csvfilepath) for csvfilepath in list_of_csvpaths]

        with self.output().open('w') as outfile:
            outfile.write("\n".join(list_of_csvpaths))

    def output(self):
        filename = os.path.split(self.zip_file)[1]
        name = os.path.splitext(filename)[0]
        rootdir = get_working_folder()
        path = os.path.join(rootdir, 'tmp','processcsv', name)
        return luigi.file.LocalTarget(path)


class GetCsvFile(luigi.ExternalTask):
    """
    """
    csvfile = luigi.Parameter()

    def output(self):
        return luigi.file.LocalTarget(self.csvfile)


class ValidMessages(luigi.Task):
    """ Takes AIS messages and runs validation functions, generating valid csv
    files in folder called 'cleancsv' at the same level as unzipped_ais_path
    """
    csvfile = luigi.Parameter()

    def requires(self):
        return GetCsvFile(self.csvfile)

    def run(self):
        LOGGER.debug("Processing {}.  Output to: {}".format(self.input().fn, self.output().fn))
        infile = self.input().fn
        outfile = self.output().fn
        produce_valid_csv_file(infile, outfile)

    def output(self):
        name = os.path.basename(self.input().fn)
        rootdir = get_working_folder()
        path = os.path.join(rootdir, 'files','cleancsv', name)
        clean_file_out = os.path.join(path)
        LOGGER.info("Clean file saved to {}".format(clean_file_out))
        return luigi.file.LocalTarget(clean_file_out)


class ValidMessagesToDatabase(CopyToTable):
    """
    """

    original_csvfile = luigi.Parameter()

    # resources = {'postgres': 1}

    null_values = (None,"")
    column_separator = ","

    host = os.environ['DBHOSTNAME']
    database = os.environ['DBNAME']
    user = os.environ['DBUSER']
    password = os.environ['DBUSERPASS']
    table = "ais_clean"

    cols = ['MMSI','Time','Message_ID','Navigational_status','SOG',
               'Longitude','Latitude','COG','Heading','IMO','Draught',
               'Destination','Vessel_Name',
               'ETA_month','ETA_day','ETA_hour','ETA_minute']
    columns = [x.lower() for x in cols]
    # LOGGER.debug("Columns: {}".format(columns))

    def requires(self):
        return ValidMessages(self.original_csvfile)

    def rows(self):
        """
        Return/yield tuples or lists corresponding to each row to be inserted.
        """
        with self.input().open('r') as csvfile:
            reader = csv.reader(csvfile)
            for row in reader:
                yield row
                # LOGGER.debug(line)
                # yield [x for x in line.strip('\n').split(',') ]

    def copy(self, cursor, clean_file):
        if isinstance(self.columns[0], six.string_types):
            column_names = self.columns
        elif len(self.columns[0]) == 2:
            column_names = [c[0] for c in self.columns]
        else:
            raise Exception('columns must consist of column strings or (column string, type string) tuples (was %r ...)' % (self.columns[0],))
        LOGGER.debug(self.columns)
        sql = "COPY {} ({}) FROM STDIN WITH (FORMAT csv, HEADER true)".format(self.table, ",".join(self.columns), clean_file)
        LOGGER.debug("File: {}".format(clean_file))
        cursor.copy_expert(sql, clean_file)

    def run(self):
        """
        Inserts data generated by rows() into target table.

        If the target table doesn't exist, self.create_table will be called to attempt to create the table.

        Normally you don't want to override this.
        """
        if not (self.table and self.columns):
            raise Exception("table and columns need to be specified")

        connection = self.output().connect()

        with self.input().open('r') as csvfile:
            for attempt in range(2):
                try:
                    cursor = connection.cursor()
                    # self.init_copy(connection)
                    self.copy(cursor, csvfile)
                    # self.post_copy(connection)
                except psycopg2.ProgrammingError as e:
                    if e.pgcode == psycopg2.errorcodes.UNDEFINED_TABLE and attempt == 0:
                        # if first attempt fails with "relation not found", try creating table
                        LOGGER.info("Creating table %s", self.table)
                        connection.reset()
                        self.create_table(connection)
                    else:
                        raise
                else:
                    break

        # mark as complete in same transaction
        self.output().touch(connection)
        # commit and clean up
        connection.commit()
        connection.close()


class LoadCleanedAIS(CopyToTable):
    """
    Execute ValidMessagesToDatabase and update ais_sources table with name of CSV processed
    """

    csvfile = luigi.Parameter()

    # resources = {'postgres': 1}

    null_values = (None,"")
    column_separator = ","

    host = os.environ['DBHOSTNAME']
    database = os.environ['DBNAME']
    user = os.environ['DBUSER']
    password = os.environ['DBUSERPASS']
    table = "ais_sources"

    def requires(self):
        return ValidMessagesToDatabase(self.csvfile)

    def run(self):
        # Prepare source data to add to ais_sources
        source_data = {'filename': self.csvfile,
                       'ext': os.path.splitext(self.csvfile)[1],
                       'invalid': 0,
                       'clean': 0,
                       'dirty': 0,
                       'source': 0}

        columns = '(' + ','.join([c.lower() for c in source_data.keys()]) + ')'

        connection = self.output().connect()
        cursor = connection.cursor()
        with cursor:
            tuplestr = "(" + ",".join("%({})s".format(i) for i in source_data.keys()) + ")"
            cursor.execute("INSERT INTO " + self.table + " "+ columns + " VALUES "+ tuplestr, source_data)

        # mark as complete
        self.output().touch(connection)

        # commit and clean up
        connection.commit()
        connection.close()

@requires(UnzippedArchive)
class WriteCsvToDb(luigi.Task):
    """
    """
    def run(self):
        list_of_csvpaths = []
        LOGGER.debug("Writing csvs from {}".format(self.input().fn))
        for csvfile in os.listdir(self.input().fn):
            if os.path.splitext(csvfile)[1] == '.csv':
                list_of_csvpaths.append(os.path.join(self.input().fn, csvfile))
        yield [LoadCleanedAIS(csvfilepath) for csvfilepath in list_of_csvpaths]

        with self.output().open('w') as outfile:
            outfile.write("\n".join(list_of_csvpaths))

    def output(self):
        filename = os.path.split(self.zip_file)[1]
        name = os.path.splitext(filename)[0]
        rootdir = get_working_folder()
        path = os.path.join(rootdir, 'tmp','writecsv', name)
        return luigi.file.LocalTarget(path)


class ProcessZipArchives(luigi.Task):
    """
    """
    folder_of_zips = luigi.Parameter(significant=True)
    shell_script = luigi.Parameter(default='../superpyrate/unzip_csvs.sh',
                                   significant=False)
    with_db = luigi.BoolParameter(significant=False)

    def requires(self):
        return GetFolderOfArchives(self.folder_of_zips)

    def run(self):
        archives = []
        LOGGER.warn("Database flag is {}".format(self.with_db))
        LOGGER.debug("ProcessZipArchives input is: {}".format(self.input().fn))
        print(self.input().fn)
        filesystem = self.input().fs
        list_of_archives = [x for x in filesystem.listdir(self.input().fn)]
        LOGGER.debug(list_of_archives)
        for archive in list_of_archives:
            if os.path.splitext(archive)[1] == '.zip':
                archives.append(archive)
        LOGGER.debug(archives)
        if self.with_db is True:
            yield [WriteCsvToDb(arc, self.shell_script) for arc in archives]
        else:
            yield [ProcessCsv(arc, self.shell_script) for arc in archives]
        with self.output().open('w') as outfile:
            outfile.write("{}".format(self.folder_of_zips))

    def output(self):
        LOGGER.debug("Folder of zips: {} with db {}".format(self.folder_of_zips,
                                                            self.with_db))
        out_folder_name = os.path.basename(self.folder_of_zips)
        root_folder = get_working_folder()
        return luigi.file.LocalTarget(os.path.join(root_folder,
                                                   'tmp',
                                                   'archives',
                                                   out_folder_name))


class MakeIndexByQuery(PostgresQuery):
    """
    """
    query = luigi.Parameter()
    table = luigi.Parameter(default='ais_clean')

    host = os.environ['DBHOSTNAME']
    database = os.environ['DBNAME']
    user = os.environ['DBUSER']
    password = os.environ['DBUSERPASS']

@requires(ProcessZipArchives)
class MakeAllIndices(luigi.Task):

    table = luigi.Parameter(default='ais_clean')
    # with_db = True

    def run(self):
        """
        """
        options = {}
        options['host'] = os.environ['DBHOSTNAME']
        options['db'] = os.environ['DBNAME']
        options['user'] = os.environ['DBUSER']
        options['pass'] = os.environ['DBUSERPASS']

        db = AISdb(options)
        with db:
            if self.table == 'ais_clean':
                indices = db.clean_db_spec['indices']
            elif self.table == 'ais_dirty':
                indices = db.dirty_db_spec['indices']
            else:
                raise NotImplemented('Table not implemented or incorrect')

        queries = []
        for idx, cols in indices:
            idxn = self.table.lower() + "_" + idx
            queries.append("CREATE INDEX IF NOT EXISTS \""+ idxn +"\" ON \""+ self.table +"\" USING btree ("+ ','.join(["\"{}\"".format(s.lower()) for s in cols]) +")")

        yield [MakeIndexByQuery(query, self.table) for query in queries]

        with self.output().open('w') as outfile:
            outfile.write(self.table)

    def output(self):
        filename = 'create_{}_indexes.txt'.format(self.table)
        rootdir = get_working_folder()
        path = os.path.join(rootdir, 'tmp','database', filename)
        return luigi.file.LocalTarget(path)

@requires(MakeAllIndices)
class ClusterAisClean(PostgresQuery):
    """Clusters the ais_clean table over the disk on the mmsi index
    """

    # with_db = True

    host = os.environ['DBHOSTNAME']
    database = os.environ['DBNAME']
    user = os.environ['DBUSER']
    password = os.environ['DBUSERPASS']
    table = "ais_clean"
    query = 'CLUSTER VERBOSE ais_clean USING ais_clean_mmsi_idx;'
