import __hpx__ as hpx
import os
import arrow
import datetime
import html
import extractors
from extractors import common

log = hpx.get_logger(__name__)

options = {
}

def get_common_data(datatypes, fpath):
    assert isinstance(datatypes, common.DataType)
    d = {}
    fpath = hpx.command.CoreFS(fpath)

    for datatype in common.DataType:
        if datatype & datatypes:
            log.info(f"Attempting with {datatype}")
            md = {}

            ex = common.extractors.get(datatype, None)
            if ex:
                try:
                    fdata = ex.file_to_dict(fpath)
                except ValueError:
                    log.info(f"Skipping {datatype}")
                    continue
                if fdata:
                    log.info(f"{datatype} matched!")
                    md.update(ex.extract(fdata))
                else:
                    log.info(f"{datatype} didn't match")
            if md:
                d.update(md)
                break
    return d

SetValue = hpx.command.Set
GalleryData = hpx.command.GalleryData
LanguageData = hpx.command.LanguageData
TitleData = hpx.command.TitleData
ArtistData = hpx.command.ArtistData
ArtistNameData = hpx.command.ArtistNameData
ParodyData = hpx.command.ParodyData
ParodyNameData = hpx.command.ParodyNameData
CircleData = hpx.command.CircleData
CategoryData = hpx.command.CategoryData
UrlData = hpx.command.UrlData
NamespaceTagData= hpx.command.NamespaceTagData
TagData= hpx.command.TagData
NamespaceData = hpx.command.NamespaceData

def apply_metadata(data, gallery, options={}):
    """
    data = {
        'titles': None, # [(title, language),...]
        'artists': None, # [(artist, (circle, circle, ..)),...]
        'parodies': None, # [parody, ...]
        'category': None,
        'tags': None, # [tag, tag, tag, ..] or {ns:[tag, tag, tag, ...]}
        'pub_date': None, # DateTime object or Arrow object
        'language': None,
        'urls': None # [url, ...]
    }
    """

    log.debug(f"data: {data}")

    gdata = GalleryData()

    if isinstance(data.get('titles'), (list, tuple, set)):
        gtitles = []
        for t, l in data['titles']:
            gtitle = None
            if t:
                t = html.unescape(t)
                gtitle = TitleData(name=t)
            if t and l:
                gtitle.language = LanguageData(name=l)
            if gtitle:
                gtitles.append(gtitle)

        if gtitles:
            gdata.titles = SetValue(gtitles)
            log.debug("applied titles")

    if isinstance(data.get('artists'), (list, tuple, set)):
        gartists = []
        for a, c in data['artists']:
            if a:
                gartist = ArtistData(names=[ArtistNameData(name=common.capitalize_text(a))])
                gartists.append(gartist)

                if c:
                    gcircles = []
                    for circlename in [x for x in c if x]:
                        gcircles.append(CircleData(name=common.capitalize_text(circlename)))
                    gartist.circles = gcircles

        if gartists:
            gdata.artists = SetValue(gartists)
            log.debug("applied artists")

    if isinstance(data.get('parodies'), (list, tuple, set)):
        gparodies = []
        for p in data['parodies']:
            if p:
                gparody = ParodyData(names=[ParodyNameData(name=common.capitalize_text(p))])
                gparodies.append(gparody)

        if gparodies:
            gdata.parodies = SetValue(gparodies)
            log.debug("applied parodies")

    if data.get('category'):
        gdata.category = SetValue(CategoryData(name=data['category']))
        log.debug("applied category")
    
    if data.get('language'):
        gdata.language = SetValue(LanguageData(name=data['language']))
        log.debug("applied language")

    if isinstance(data.get('tags'), (dict, list)):
        if isinstance(data['tags'], list):
            data['tags'] = {None: data['tags']}
        gnstags = []
        for ns, tags in data['tags'].items():
            if ns is not None:
                ns = ns.strip()
            if ns and ns.lower() == 'misc':
                ns = None
            for t in tags:
                t = t.strip()
                if t:
                    kw = {'tag': TagData(name=t)}
                    if ns:
                        kw['namespace'] = NamespaceData(name=ns)
                    gnstags.append(NamespaceTagData(**kw))

        if gnstags:
            gdata.tags = SetValue(gnstags)
            log.debug("applied tags")

    if isinstance(data.get('pub_date'), (datetime.datetime, arrow.Arrow)):
        pub_date = data['pub_date']
        gdata.pub_date = SetValue(pub_date)
        log.debug("applied pub_date")

    if isinstance(data.get('urls'), (list, tuple)):
        gurls = []
        for u in data['urls']:
            if u:
                gurls.append(UrlData(name=u))
        if gurls:
            gdata.urls = SetValue(gurls)
            log.debug("applied urls")

    applied = hpx.command.UpdateItemData(gallery, gdata, options=options)

    log.debug(f"applied: {applied}")

    return applied
    
@hpx.subscribe("init")
def inited():
    common.plugin_config.update(hpx.get_plugin_config())

@hpx.subscribe('config_update')
def config_update(cfg):
    common.plugin_config.update(cfg)

@hpx.attach("GalleryFS.parse_metadata_file")
def parse(path, gallery):
    fs = hpx.command.CoreFS(path)

    contents = {x: os.path.split(x)[1].lower() for x in fs.contents(corefs=False) if x.lower().endswith(common.filetypes)}
    log.debug(f"Contents for {fs.path}:")
    log.debug(f"{tuple(contents.values())}")

    cdata = common.common_data.copy()

    applied = False

    for fnames, dtypes in common.filenames.items():
        for fpath, fname in contents.items():
            if fname in fnames:
                log.debug(f"path: {fpath}")
                d = get_common_data(dtypes, fpath)
                if d:
                    applied = True
                    cdata.update(d)
                break
    if applied:
        apply_metadata(cdata, gallery)
        
    return applied

# This is work in progress to turn this plugin into a regular metadata handler too

# @hpx.attach("Metadata.info")
# def metadata_info():
#     return hpx.command.MetadataInfo(
#         identifier = "filemetadata",
#         batch = 25,
#         name = "File Metadata",
#         description = "Extracts and applies metadata from a file accompanying a gallery. Supports files produced from eze, e-hentai-downloader and hdoujin",
#         models = (
#             hpx.command.GetDatabaseModel("Gallery"),
#         )
#     )

# def query(itemtuple, login_site=URLS['eh']):
#     "Looks up files for matching items"
#     mdata = []

#     # get exhentai login session if applicable
#     ex_login = hpx.command.GetLoginStatus(login_site) if "exhentai" in login_site else False
#     login_session = None
#     if ex_login:
#         login_session = hpx.command.GetLoginSession(login_site)
#     if login_site == 'exhentai':
#         log.info(f"logged in to exhentai: {ex_login}")

#     for mitem in itemtuple:
#         gurls = [] # tuple of (title, url)

#         url = mitem.url
#         item = mitem.item
#         options = mitem.options

#         # url was provided
#         if url:
#             log.info(f"url provided: {url} for {item}")
#             gurls.append((url, url))
#         else: # manually search for id
#             log.info(f"url not provided for {item}")
#             if (ex_login if "exhentai" in login_site else True):
#                 # search with title
#                 i_title = ""
#                 i_hash = ""
#                 if PLUGIN_CONFIG.get("filename_search"):
#                     sources = item.get_sources()
#                     if sources:
#                         # get folder/file name
#                         i_title = os.path.split(sources[0])[1]
#                         # remove ext
#                         i_title = os.path.splitext(i_title)[0]
#                 else:
#                     if item.titles:
#                         i_title = item.titles[0].name # make user choice
#                 if i_title:
#                     gurls = title_search(i_title, ex='exhentai' in login_site, session=login_session)

#                 # TODO: search with hash
#                 if not gurls:
#                     pass

#         log.info(f"found {len(gurls)} urls for item: {item}")

#         # list is sorted by date added so we reverse it
#         gurls.reverse()

#         log.debug(f"{gurls}")
#         final_gurls = []
#         # TODO: maybe prefer language of gallery first?
#         pref_lang = PLUGIN_CONFIG.get('preferred_language')
#         if pref_lang:
#             for t in gurls:
#                 if pref_lang.lower() in t[0].lower():
#                     final_gurls.insert(0, t)
#                     continue
#                 final_gurls.append(t)
#         else:
#             final_gurls = gurls

#         for t, u in final_gurls:
#             g_id, g_token = parse_url(u)
#             if g_id and g_token:
#                 mdata.append(hpx.command.MetadataData(
#                     metadataitem=mitem,
#                     title=t,
#                     url=u,
#                     data={
#                         'gallery': [g_id, g_token],
#                         'gallery_url': u,
#                         }))
#     log.info(f"Returning {len(mdata)} data items")
#     return tuple(mdata)