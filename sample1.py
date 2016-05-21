import os
import json
import keystoneclient.v3 as keystoneclient
import swiftclient.client as swiftclient
from flask import Flask
from flask import render_template
from flask import request
from werkzeug import secure_filename
import hashlib
import couchdb
import time
try:
  from SimpleHTTPServer import SimpleHTTPRequestHandler as Handler
  from SocketServer import TCPServer as Server
except ImportError:
  from http.server import SimpleHTTPRequestHandler as Handler
  from http.server import HTTPServer as Server


UPLOAD_FOLDER = 'uploads/'
ALLOWED_DOC = set(['txt'])

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

USERNAME = '215ae482-4765-4bce-81b2-3261508e6eac-bluemix'
PASSWORD = 'c69af658ce22356e4d61557e7e6e39c8931d311c3c6df0865386e6facf79b08f'
HOST = '215ae482-4765-4bce-81b2-3261508e6eac-bluemix.cloudant.com'
URL = 'https://' + USERNAME + ':' + PASSWORD + '@' + HOST

# connecting with server
couch = couchdb.Server(URL)
couch.resource.credentials = (USERNAME, PASSWORD)
dbname = 'test1'
db = couch[dbname]


@app.route('/')
def startapp():
      documents = display_documents()
      return render_template('main.html',istable=True,document=documents)      


# display the documents present in the server
def display_documents():
  retValue = []
  for doc in db:
    docum = db[doc]
    retValue.append( 
                    { 'filename' : docum['filename'],
                      'content' : docum['content'],
                      'hashvalue' : docum['hashvalue'],
                      'last_modified_date' : docum['last_modified_date'],
                      'revision' : docum['_rev']
                    })
  return retValue

# hash the content of the file
def gethashContent(fcontent):
      # create an hash object for sha224
      return hashlib.sha224(fcontent).hexdigest()
      

# get the file name from the file object
def get_filename(fileobj):
    return fileobj.filename

# return the file contents
def get_file_content(fileobj):
    filename = get_filename(fileobj)
    content = fileobj.read()
    '''
    # save the file into uploads folder
    fileobj.save(os.path.join(app.config['UPLOAD_FOLDER'],filename))
    # open the file and read the contents
    with open(os.path.join(app.config['UPLOAD_FOLDER'],filename),'rb') as fileobject:
          content = fileobject.read()
    remove_temp_file(fileobj)
    '''
    return content

# deleting the file
def remove_temp_file(fileobj):
    filename = get_filename(fileobj)
    os.unlink(os.path.join(app.config['UPLOAD_FOLDER'],filename))


# Upload new files to Cloudant server
def upload_file(filename,content, hashcontent):
     now = time.strftime("%c")
     doc_id, doc_rev = db.save({
                               'filename': filename,
                               'content' : content,
                               'hashvalue': hashcontent,
                               'last_modified_date' : now
                               })

# Upload new attachment file to Cloudant server
def upload_attachment(filename,content,hashcontent):
  now = time.strftime("%c")
  doc_id, doc_rev = db.save({
                               'filename': filename,
                               'content' : 'please check attachment',
                               'hashvalue': hashcontent,
                               'last_modified_date' : now
                               })
  
  db.put_attachment(db[doc_id],content,filename=filename,content_type=None)

# updating existing file
def update_file(filename,fcontent,hashcontent):
    now = time.strftime("%c")
    doc_id,doc_rev = db.save({
                              'filename' : filename,
                              'content' : fcontent,
                              'hashvalue' : hashcontent,
                              'last_modified_date' : now
                            })
    return get_revision_filename(filename)


# Get revision history based on filename
def get_revision_filename(filename):
    revision_numbers = []
    for doc_id in db:
        doc = db[doc_id]
        if doc['filename'] == filename:
            revision_numbers.append(doc['_rev'])
    return revision_numbers

# check to see if file name exists
def filename_exists(filename):
    docum_id = []
    isfilepresent = False
    for doc_id in db:
        document = db[doc_id]
        if document['filename'] == filename:
            isfilepresent = True
            docum_id.append(doc_id)
    return (isfilepresent , docum_id)


# check hashcontent is the same
def same_hashcontent(hashcontent,docm_id):
    for doc_id in docm_id:
      document = db[doc_id]
      if hashcontent == document['hashvalue']:
          return True
    return False


# Upload or Update file condition
# 1. Upload file if that file name is not present in server
# 2. Update file if filename is present but file content is different
# 3. Dont update file if filename is present and file content is same in server
def upload_or_update_file(fileobj):
    # check to see if file exists or not
    filename = get_filename(fileobj)
    fcontent = get_file_content(fileobj)
    return fcontent

# method to get the document based on filename and download it to the local system
@app.route('/download', methods=['GET','POST'])
def download_file():
    print "download_file clicked"
    if request.method == 'POST':
        print "inside post method"
        filename = request.form['dfilename']
        revision = request.form['dversion']
        filename = secure_filename(filename)
        final_content = ''
        downloadfilename =  os.path.join(os.getcwd(),"static","downloads",filename)
        for doc_id in db:
            document = db[doc_id]
            if filename == document['filename'] and revision == document['_rev']:
                # check to see doc has an attachment
                if document['content'] == 'please check attachment':
                    fcontent = db.get_attachment(doc_id,filename,default='no file')
                    if fcontent == 'no file':
                      return "Not able to retrieve attachment"
                    else:
                      final_content = fcontent.read()
                # if this is not an attachment
                else:
                    final_content = document['content']                
                fileobj = open(downloadfilename,'wb')
                fileobj.write(final_content)
                fileobj.close()
                break
        return render_template('download.html',filename=filename)
                

@app.route('/deleted', methods=['GET','POST'])
def delete_file():
  if request.method == 'POST':
      del_filename = request.form['del_filename']
      del_version = request.form['del_version']
      del_filename = secure_filename(del_filename)
      del_doc_id = ''
      for doc_id in db:
          document = db[doc_id]
          if del_filename == document['filename'] and del_version == document['_rev']:
              del_doc_id = doc_id
              break
      if del_doc_id == '':
          return "Filename="+ del_filename + " with this version number=" + del_version +" does not exist!.."
      del_doc = db[del_doc_id]
      db.delete(del_doc)
      documents = display_documents()
      return "Filename=" + del_filename + " has been deleted!.."

@app.route('/', methods=['GET','POST'])
def submit_click():
        if request.method == 'POST':
                #access the uploaded file
                file = request.files['file']
                # determine if we need to upload or update the file
                print 'recieved file object need to determine if upload or update is needed in filename=' + file.filename
                return upload_or_update_file(file)
        return "Not applicable"

port = os.getenv('VCAP_APP_PORT', '5000')
if __name__ == "__main__":
        app.run(host='0.0.0.0', port=int(port),debug=True)

