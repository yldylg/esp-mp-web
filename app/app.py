import uos as os
from http import Server, route


@route('/listdir', method='GET', minetype='application/json')
def handle_hello_msg(r):
	path = r.params.get('path') or '.'
	if not path.endswith('/'):
		path += '/'
	data = []
	field = ['mode', 'ino', 'dev', 'nlink', 'uid', 'gid', 'size', 'atime', 'mtime', 'ctime']
	for name in sorted(os.listdir(path)):
		try:
			stat = os.stat(path + name)
			data.append(dict(name=name, path=path + name, **{k:v for k, v in zip(field, stat)}))
		except:
			continue
	return dict(code=0, msg='ok', data=data)

@route('/read', method='GET', minetype='application/json')
def do_exit(r):
	path = r.params.get('path')
	offset = r.params.get('offset') or 0
	size = r.params.get('size') or -1
	try:
		with open(path, 'rb') as f:
			f.seek(offset)
			data = f.read(size)
		return dict(code=0, data=data)
	except Exception as e:
		return dict(code=-1, msg=e)

@route('/write', method='POST', minetype='application/json')
def up_msg(r):
	return dict(code=0, msg='up', data=r.read())

srv = Server(host='0.0.0.0', port=80, root='./web/')
srv.start()
