import sys
from arlo import Arlo
from dropbox import Dropbox
from dropbox.files import WriteMode
from dropbox.exceptions import ApiError
import datetime
import regex as re
from PIL import Image
import io
import click


@click.group(chain=True, invoke_without_command=True)
@click.pass_context
def cli(ctx):
    # ensure that ctx.obj exists and is a dict
    ctx.ensure_object(dict)
    pass


@cli.command('click-picture', short_help='click picture using Arlo camera')
@click.argument('folder', type=click.Path(exists=True, dir_okay=True))#, help='folder to copy image to')
@click.argument('filetag', required=True)#, help='filename prefix, typically followed by a timestamp')
@click.option('--username', prompt='Username for Arlo service')
@click.password_option()
@click.pass_context
def click_picture_from_arlo(
        ctx,
        folder,
        filetag,
        username,
        password):
    # Instantiating the Arlo object automatically calls Login(),
    # which returns an oAuth token that gets cached.
    # Subsequent successful calls to login will update the oAuth token.
    arlo = Arlo(username, password)

    # Get the list of devices and filter on device type to only get the basestation.
    # This will return an array which includes all of the basestation's associated metadata.
    basestations = arlo.GetDevices('basestation')
    # Get the list of devices and filter on device type to only get the camera.
    # This will return an array which includes all of the camera's associated metadata.
    cameras = arlo.GetDevices('camera')

    # Tells the Arlo basestation to trigger a snapshot on the given camera.
    # This snapshot is not instantaneous, so this method waits for the response and returns the url
    # for the snapshot, which is stored on the Amazon AWS servers.
    snapshot_url = arlo.TriggerFullFrameSnapshot(basestations[0], cameras[0])

    # This method requests the snapshot for the given url and writes the image data to the location specified.
    # Note: Snapshots are in .jpg format.
    timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    filename = filetag + '_' + str(timestamp) + '.jpg'
    filepath = folder + '\\' + filename
    arlo.DownloadSnapshot(snapshot_url, filepath)
    ctx.obj['path-to-picture'] = filepath
    ctx.obj['filename'] = filename
    print('Downloaded snapshot to ' + filepath)


@cli.command('rotate-image', short_help='rotate by angle')
@click.argument('angle', required=True, type=click.Choice(['90', '180', '270']))
@click.pass_context
def rotate_image(
        ctx,
        angle):
    """
    :param angle: choice of 90, 180, 270. Written as string, as int is not supported as choice.
    See https://github.com/pallets/click/issues/784.
    """
    filepath = ctx.obj['path-to-picture']
    print('Rotating image at ' + filepath + ' to angle ' + angle)
    image = Image.open(filepath)
    image = image.rotate(int(angle), expand=1)
    image.save(filepath)
    print('Rotated image at ' + filepath)


@cli.command('upload-to-dropbox')
@click.option('--token', nargs=1)
@click.argument('folder-name', required=True, type=str)
@click.pass_context
def upload_to_dropbox(
        ctx,
        token,
        folder_name):
    filename = ctx.obj['filename']
    filepath = ctx.obj['path-to-picture']
    dropbox = Dropbox(token)
    targetfile = ('/' + folder_name + '/' + filename)
    image = Image.open(filepath)
    imageIO = io.BytesIO()
    image.save(imageIO, format='JPEG')
    try:
        dropbox.files_upload(imageIO.getvalue(), targetfile, mode=WriteMode('overwrite'))
    except ApiError as err:
        # This checks for the specific error where a user doesn't have enough Dropbox space quota to upload this file
        if (err.error.is_path() and
                err.error.get_path().error.is_insufficient_space()):
            sys.exit("ERROR: Cannot back up; insufficient space.")
        elif err.user_message_text:
            print(err.user_message_text)
            sys.exit()
        else:
            print(err)
            sys.exit()
    # create a shared link
    link = dropbox.sharing_create_shared_link(targetfile)
    url = link.url
    # link which directly downloads by replacing ?dl=0 with ?dl=1
    dl_url = re.sub(r"\?dl\=0", "?dl=1", url)
    print('done uploading file ' + filename + ' to ' + dl_url)


if __name__ == '__main__':
    try:
        cli(obj={})
    except Exception as e:
        print(e)
        raise

