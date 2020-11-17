from typing import List, Mapping, Dict, Any, cast, Tuple, Optional
import session
import webserver
from PIL import Image

def scrub_name(s: str) -> str:
    s = s[:100]
    s = s.replace('&', '&amp;')
    s = s.replace('<', '&lt;')
    s = s.replace('>', '&gt;')
    return s

# Load the feed page
with open('account.html') as f:
    lines = f.readlines()
    account_page = ''.join(lines)

def do_ajax(ob: Mapping[str, Any], session_id: str) -> Dict[str, Any]:
    sess = session.get_session(session_id)
    account = sess.active_account
    act = ob['act']
    if act == 'logout':
        sess.switch_account('')
        return { 'reload': True }
    elif act == 'switch':
        sess.switch_account(ob['name'])
        return { 'reload': True }
    elif act == 'change_name':
        newname = scrub_name(ob['name'])
        account.name = newname
    elif act == 'change_pw':
        account.password = ob['pw']
        return { 'have_pw': len(account.password) > 0 }
    else:
        raise RuntimeError('unrecognized action')
    return {}

def do_account(query: Mapping[str, Any], session_id: str) -> str:
    sess = session.get_session(session_id)
    account = sess.active_account
    globals = [
        'let session_id = \'', session_id, '\';\n',
        'let username = \'', account.name, '\';\n',
        'let profile_pic = \'', account.image, '\';\n',
        'let have_pw = ', 'true' if len(account.password) > 0 else 'false', ';\n',
        'let account_names = ', str([a.name for a in sess.accounts]), ';\n',
        'let account_images = ', str([a.image for a in sess.accounts]), ';\n',
    ]
    updated_account_page = account_page.replace('//<globals>//', ''.join(globals), 1)
    return updated_account_page

def do_error_page(err: str, session_id: str) -> str:
    return f'<html><body>{err}</body></html>'

def receive_image(query: Mapping[str, Any], session_id: str) -> str:
    account = session.get_session(session_id).active_account

    # Receive the file
    temp_filename = f'/tmp/{account.id}.jpeg'
    try:
        webserver.sws.receive_file(temp_filename, 4000000)
    except Exception as e:
        return do_error_page(str(e), session_id)

    # Scale and crop the image
    img = Image.open(temp_filename)
    img = img.resize((48 * img.size[0] // img.size[1], 48), Image.ANTIALIAS)
    img = img.convert('RGB')
    if img.size[0] > 64:
    	left = (img.size[0] - 64) / 2
    	img = img.crop((left, 0, left + 64, 48))
    final_filename = f'profile_pics/{account.id}.jpeg'
    img.save(final_filename)

    # Update the profile pic
    account.image = final_filename
    return do_account(query, session_id)
