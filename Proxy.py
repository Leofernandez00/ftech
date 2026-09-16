import http.server
import socketserver
import requests

# Dicionário para armazenar os usuários e suas permissões
user_permissions = {
    'user1': {'allowed_sites': ['example.com']},
    'user2': {'allowed_sites': ['example.org']}
}


# Classe de Manipulador de Proxy
class Proxy(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        user = self.headers.get('User')
        if user not in user_permissions:
            self.send_error(403, 'Forbidden')
            return

        site = self.path.split('/')[2]
        if site not in user_permissions[user]['allowed_sites']:
            self.send_error(403, 'Forbidden')
            return

        response = requests.get(self.path[1:])
        self.send_response(response.status_code)
        for key, value in response.headers.items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(response.content)


def run(server_class=http.server.HTTPServer, handler_class=Proxy, port=8080):
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    print(f'Starting proxy server on port {port}...')
    httpd.serve_forever()


if __name__ == '__main__':
    run()
