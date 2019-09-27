from http import Server, route


@route('/hello', method='GET', minetype='application/json')
def handle_hello_msg(r):
	return dict(code=0, msg='hello')

@route('/up', method='POST', minetype='application/json')
def up_msg(r):
	return dict(code=0, msg='up', data=r.read())

@route('/exit', method='GET', minetype='application/json')
def do_exit(r):
	srv.stop()
	return dict(code=0, msg='exited')

srv = Server(host='0.0.0.0', port=80, root='./web/')
srv.start()
