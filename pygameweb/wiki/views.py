from flask import (Blueprint, render_template, abort,
                   redirect, url_for, request, Response)
# http://flask-sqlalchemy-session.readthedocs.org/en/v1.1/
from flask_sqlalchemy_session import current_session
import ghdiff
from flask_security import login_required, roles_required

from pygameweb.wiki.models import Wiki
from pygameweb.wiki.forms import WikiForm


wiki_blueprint = Blueprint('wiki',
                           __name__,
                           template_folder='../templates/')


def wiki_for(link):
    """ Returns a wiki object for the given link.
    """
    result = (current_session
              .query(Wiki)
              .filter(Wiki.link == link)
              .filter(Wiki.latest == 1)
              .first())

    if not result:
        abort(404)
    return result


@wiki_blueprint.route('/wiki/', methods=['GET'])
@wiki_blueprint.route('/wiki/<link>', methods=['GET'])
def index(link='index'):
    """ of the wiki page.
    """
    # legacy urls used action var.
    action = request.args.get('action', '')

    if action == 'source':
        return source(link)
    elif action == 'history':
        return history(link)
    elif action == 'diff':
        return diff(link)
    elif action == 'meta':
        # edit meta data.
        pass
    elif action == 'links':
        # show back links
        pass

    return render_template('wiki/view.html', link=link, wiki_for=wiki_for)


@wiki_blueprint.route('/wiki/<link>/revert', methods=['GET'])
@login_required
@roles_required('members')
def revert(link):
    """ the link to make the latest version the one selected.
    """

    latest = request.args.get('latest', None)
    if latest is not None:
        oldone = wiki_for(link)
        newone = (current_session
                  .query(Wiki)
                  .filter(Wiki.link == link)
                  .filter(Wiki.id == int(latest))
                  .first())

        oldone.latest = 0
        newone.latest = 1
        current_session.add(newone)
        current_session.add(oldone)
        current_session.commit()
        return redirect(url_for('wiki.index', link=link, id=newone.id))
    else:
        abort(404)


@wiki_blueprint.route('/wiki/<link>/source', methods=['GET'])
def source(link):
    """ of the wiki page using a text/plain mime type.
    """
    # if id=, use that one.
    the_id = request.args.get('id', '')
    if the_id:
        result = (current_session
                  .query(Wiki)
                  .filter(Wiki.id == int(the_id))
                  .first())
        if not result:
            abort(404)
    else:
        result = wiki_for(link)

    return Response(result.content, mimetype='text/plain')


@wiki_blueprint.route('/wiki/<link>/history', methods=['GET'])
@login_required
@roles_required('members')
def history(link):
    """ for the wiki page with all the changes.
    """
    result = wiki_for(link)
    versions = (current_session
                .query(Wiki)
                .filter(Wiki.link == link)
                .order_by(Wiki.id.desc())
                .all())

    return render_template('wiki/history.html', versions=versions, wiki=result)


@wiki_blueprint.route('/wiki/<link>/diff', methods=['GET'])
def diff(link):
    """ two pages (newid, and oldid) and show the changes.
    """
    result = wiki_for(link)

    new_id = request.args.get('newid', None)
    old_id = request.args.get('oldid', None)
    if new_id is not None and old_id is not None:
        new_id = int(new_id)
        old_id = int(old_id)

        results = (current_session
                   .query(Wiki)
                   .filter(Wiki.id.in_([new_id, old_id]))
                   .all())
        if not results or len(results) != 2:
            abort(404)

        old_wiki = [o for o in results if o.id == old_id][0]
        new_wiki = [o for o in results if o.id == new_id][0]

        html_diff = ghdiff.diff(old_wiki.content_rendered,
                                new_wiki.content_rendered)
    else:
        abort(404)

    return render_template('wiki/diff.html', wiki=result, html_diff=html_diff)


@wiki_blueprint.route('/wiki/<link>/edit', methods=['GET', 'POST'])
@login_required
@roles_required('members')
def edit(link):
    """ the wiki page.
    """

    # TODO: we need to add users_id, parents, and keywords
    page = (current_session
            .query(Wiki)
            .filter(Wiki.link == link)
            .filter(Wiki.latest == 1)
            .first())
    if page is None:
        # we create a new empty wiki page!
        page = Wiki(link=link, title=link, latest=1)

    form = WikiForm(obj=page)

    if request.method == 'GET':
        # we want people to enter in new data for this field.
        form.changes.data = ''
    elif request.method == 'POST':
        if form.validate_on_submit():
            page.new_version(current_session)
            page.content = form.content.data
            page.changes = form.changes.data
            current_session.add(page)
            current_session.commit()

            return redirect(url_for('wiki.index', link=page.link))
    return render_template('wiki/edit.html', form=form, wiki=page)


def add_wiki_blueprint(app):
    """ to the app.
    """
    app.register_blueprint(wiki_blueprint)
