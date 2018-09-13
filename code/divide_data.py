import sys
import tarfile
import time
from datetime import datetime

from config import LINES_PER_LAMBDA, s3_client, data_s3_client
from itertools import zip_longest
from direct_write import s3_determine_app_store

'''
Takes a file and subdivides it into chunks that we can process in a single Lambda function

'''

def find_most_recent_object(bucket, prefix):
	all_objects = data_s3_client.list_objects(Bucket = bucket, Prefix = prefix)
	most_recent_key = ''
	most_recent_datetime = datetime(2000, 1, 1)
	for obj in all_objects['Contents']:
		if obj['LastModified'].timestamp() > most_recent_datetime.timestamp():
			most_recent_key = obj['Key']
			most_recent_datetime = obj['LastModified']
	print("Most recent object is ", most_recent_key)
	return most_recent_key


	
def s3_break_up_file(data, s3_bucket, start_line_number = 0):
	'''
	Function to interact with splitting up an s3 object and then writing it into an s3 object instead of text files locally
	'''
	print("Breaking up data into smaller files...")

	start_time = time.time()

	data_iterator = data.iter_lines()

	tar = tarfile.open(mode = 'r|gz', fileobj = data)

	app_store = ''
	curr_chunk = []
	chunk_number = 0
	count = 0
	for entry in tar:
		file_obj = tar.extractfile(entry)
		line_number = 0
		for line in file_obj:
			line_number += 1
			if line_number < start_line_number:
				continue
			if app_store == '':
				app_store = s3_determine_app_store(line.decode('utf-8'))
			curr_chunk.append(line.decode('utf-8'))
			if count == LINES_PER_LAMBDA:
				curr_chunk_string = ''.join(curr_chunk)
				curr_chunk_bytes = curr_chunk_string.encode('utf-8')
				object_name = 'adstxt/app_lambda_file_' + app_store +'_' + str(line_number) + '.txt'
				response = s3_client.put_object(Body = curr_chunk_bytes, Bucket = s3_bucket, Key = object_name)

				#reset chunk
				curr_chunk = []
				#reset count
				count = 0
				#increase chunk number
				chunk_number += 1
			else:
				count += 1

			if time.time() - start_time > 60 * 4 + 50 and len(curr_chunk) > 0: #time limit of 4 minutes 50 seconds for lambda function processing

				#process this chunk into a text file
				curr_chunk_string = ''.join(curr_chunk)
				curr_chunk_bytes = curr_chunk_string.encode('utf-8')
				object_name = 'adstxt/app_lambda_file_' + app_store +'_' + str(line_number) + '.txt'
				response = s3_client.put_object(Body = curr_chunk_bytes, Bucket = s3_bucket, Key = object_name)

				#return the line_number to start the next one at
				return line_number


	#check if there's an incomplete chunk near end and if so, we want to process that too
	if len(curr_chunk) > 0:
		curr_chunk_string = ''.join(curr_chunk)
		curr_chunk_bytes = curr_chunk_string.encode('utf-8')
		object_name = 'adstxt/app_lambda_file_' + app_store +'_' + str(line_number) + '.txt'
		response = s3_client.put_object(Body = curr_chunk_bytes, Bucket = s3_bucket, Key = object_name)

	print("Done creating smaller files.")
	return 0
