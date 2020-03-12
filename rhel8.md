# Red Hat Enterprise Linux 8 / CentOS 8 installation guide (draft)

1.  Install O.S. packages

    `dnf install libxml2-devel openssl-devel nss gcc libcurl-devel python3-pycurl python36-devel python36`

2.  Create virtual environment python

    `python -m venv env`

3.  Activate virtual environment

    `source env/bin/activate`

4.  Export and Install pycurl

    `export PYCURL_SSL_LIBRARY=openssl && pip install --no-cache-dir pycurl`
