# main.py
import __hpx__ as hpx
import pickle
import os

from bs4 import BeautifulSoup

log = hpx.get_logger("main")



current_user_name = ""
status_text = ""
response = None
user_dict = None

save_file = os.path.join(hpx.constants.current_dir, '.info')

default_delay = 8

HEADERS = {'user-agent':"Mozilla/5.0 (Windows NT 6.3; rv:36.0) Gecko/20100101 Firefox/36.0"}

match_url_prefix = r"^(http\:\/\/|https\:\/\/)?(www\.)?" # http:// or https:// + www.
match_url_end = r"\/?$"

url_regex =  match_url_prefix + r"((exhentai|(g\.)?e-hentai)\.org)" + match_url_end

MAIN_URLS = {
    'eh': "https://e-hentai.org",
    'ex': "https://exhentai.org"
}

URLS = MAIN_URLS
URLS.update({
    'login': "https://e-hentai.org/home.php"
})

@hpx.subscribe("init")
def inited():
    # set default delay values if not set
    delays = hpx.get_setting("network", "delays", {})
    for u in (MAIN_URLS['ex'], MAIN_URLS['eh']):
        if u not in delays:
            log.info(f"Setting delay on {u} requests to {default_delay}")
            delays[u] = default_delay
            hpx.update_setting("network", "delays", delays)

    # retrieve saved user info
    if os.path.exists(save_file):
        with open(save_file, "rb") as f:
            user_dict = pickle.load(f)
        if user_dict:
            log.info(str(user_dict))
            login(user_dict, {})
            if response is not None:
                log.info("Successfully re-logged in")

@hpx.subscribe("disable")
def disabled():
    save_user_dict()

@hpx.subscribe("remove")
def removed():
    pass

@hpx.attach("Login.info")
def login_info():
    return hpx.command.LoginInfo(
        identifier = "ehentai",
        name = "EHentai",
        parser = url_regex,
        sites = ("www.e-hentai.org", "www.exhentai.org"),
        description = "Login to E-Hentai & ExHentai",
    )

@hpx.attach("Login.login", trigger="ehentai")
def login(userpass, options):
    global current_user_name
    global status_text
    global response
    global user_dict

    user_dict = userpass
    response = None
    current_user_name = ""

    ipb_member = userpass.get('ipb_member_id', "")
    ipb_pass = userpass.get('ipb_pass_hash', "")
    if ipb_member and ipb_pass:

        cookies = {}
        # get user input
        cookies.update({
            'ipb_member_id': ipb_member,
            'ipb_pass_hash': ipb_pass,
        })

        # prepare request
        req_props = hpx.command.RequestProperties(
            session=True,
            cookies=cookies,
            headers=HEADERS
            )

        req = hpx.command.SingleGETRequest()

        # check ehentai.org/home.php
        r = req.request(URLS['login'], req_props)

        if r.ok:
            bad_access, msg = check_access(r)
            status_text = msg
            if not bad_access:
                if userpass.get("exhentai", True):
                    # check exhentai
                    req_props.session = r.session
                    r = req.request(URLS['ex'], req_props)
                    if r.ok:
                        bad_access, status_text = check_access(r, ex=True)
                    else:
                        status_text = "Could not access ExHentai"

                response = r

                current_user_name = ipb_member
                save_user_dict()
            
        else:
            status_text = r.reason

    else:
        status_text = "No user credentials provided"

    return response

@hpx.attach("Login.status", trigger="ehentai")
def status(options):
    return status_text

@hpx.attach("Login.logged_in", trigger="ehentai")
def logged_in(options):
    if response:
        return True
    return False

@hpx.attach("Login.response", trigger="ehentai")
def response_(options):
    return response

@hpx.attach("Login.current_user", trigger="ehentai")
def current_user(options):
    return current_user_name

def check_access(r, ex=False):
    msg = ""
    bad_access = False
    content_type = r.headers['content-type']
    text = r.text
    if 'image/gif' in content_type:
        msg = "No access to ExHentai"
    elif 'text/html' and 'Your IP address has been' in text:
        msg = text
        bad_access = True

    if not bad_access and not ex:
        soup = BeautifulSoup(text, "html.parser")
        if soup.find("div", class_="homebox"): # we have access to home.php
            pass
        elif soup.find("form"): # login page
            bad_access = True
            msg = "Wrong credentials!"
    if msg:
        log.info(f"MSG: {msg}")
    return bad_access, msg

def save_user_dict():
    global user_dict

    # save user info
    if user_dict:
        with open(save_file, "wb") as f:
            user_dict = pickle.dump(user_dict, f)
