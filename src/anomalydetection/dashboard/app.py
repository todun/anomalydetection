# -*- coding: utf-8 -*-

import os

from tornado import ioloop
from tornado.web import Application

from anomalydetection.dashboard.urls import urls
from anomalydetection.dashboard.settings import settings

# Configure app with settings and urls
app = Application(urls, **settings)

# Main, start server
if __name__ == '__main__':

    # Start server
    port = os.getenv("PORT", "5000")
    print("Server listening on port: %s" % port)
    app.listen(int(port))
    ioloop.IOLoop.current().start()