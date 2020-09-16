from api import app as application

def main():
    application.run(host='localhost', port=5002, debug=True)

if __name__ == '__main__':
    main()
