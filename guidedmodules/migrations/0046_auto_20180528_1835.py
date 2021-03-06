# Generated by Django 2.0.5 on 2018-05-28 18:35

from django.db import migrations, models
import jsonfield.fields

def forward(apps, schema_editor):
    # Move information from ModuleAssetPack to AppInstance model.
    ModuleAssetPack = apps.get_model("guidedmodules", "ModuleAssetPack")
    AppInstance = apps.get_model("guidedmodules", "AppInstance")
    for appinst in AppInstance.objects.all():
        assetpacks = ModuleAssetPack.objects.filter(module__app=appinst).distinct()
        if len(assetpacks) > 1:
            raise ValueError("{} has more than one ModuleAssetPack: {}".format(appinst, assetpacks))
        elif len(assetpacks) == 0:
            appinst.asset_paths = { }
            appinst.save(update_fields=['asset_paths'])
        else:
            assetpack = assetpacks.first()
            appinst.asset_files.set(assetpack.assets.all())
            appinst.asset_paths = assetpack.paths
            appinst.trust_assets = assetpack.trust_assets
            appinst.save(update_fields=['asset_paths', 'trust_assets'])

def backward(apps, schema_editor):
    # Move information from AppInstance model to a new ModuleAssetPack instance
    # for each AppInstance that has assets and assign the ModuleAssetPack
    # to all of the Modules in the AppInstance.
    Module = apps.get_model("guidedmodules", "Module")
    ModuleAssetPack = apps.get_model("guidedmodules", "ModuleAssetPack")
    AppInstance = apps.get_model("guidedmodules", "AppInstance")
    for appinst in AppInstance.objects.all():
        if appinst.asset_paths:
            # Compute the 'total_hash' field.
            import hashlib, json
            m = hashlib.sha256()
            m.update(
                json.dumps({
                        "trust_assets": appinst.trust_assets,
                        "basepath": "/",
                        "paths": appinst.asset_paths,
                    },
                    sort_keys=True,
                ).encode("utf8")
            )
            total_hash = m.hexdigest()

            # Get an existing ModuleAssetPack with that total_hash
            # if one exists, otherwise make a new one.
            assetpack, is_new = ModuleAssetPack.objects.get_or_create(
                source=appinst.source,
                total_hash=total_hash,
                defaults={
                    "basepath": "/",
                    "paths": appinst.asset_paths,
                    "trust_assets": appinst.trust_assets,
                }
            )
            if is_new:
                # Add its assets.
                assetpack.assets.set(appinst.asset_files.all())
    
            # Assign to all modules.
            Module.objects.filter(app=appinst)\
                .update(assets=assetpack)

class Migration(migrations.Migration):

    dependencies = [
        ('guidedmodules', '0045_auto_20180522_2048'),
    ]

    operations = [
        migrations.AddField(
            model_name='appinstance',
            name='asset_files',
            field=models.ManyToManyField(help_text='The assets linked to this pack.', to='guidedmodules.ModuleAsset'),
        ),
        migrations.AddField(
            model_name='appinstance',
            name='asset_paths',
            field=jsonfield.fields.JSONField(default={ }, help_text='A dictionary mapping file paths to the content_hashes of assets included in the assets field of this instance.'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='appinstance',
            name='trust_assets',
            field=models.BooleanField(default=False, help_text='Are assets trusted? Assets include Javascript that will be served on our domain, Python code included with Modules, and Jinja2 templates in Modules.'),
        ),
        migrations.RunPython(forward, backward),
        migrations.AlterUniqueTogether(
            name='moduleassetpack',
            unique_together=set(),
        ),
        migrations.RemoveField(
            model_name='moduleassetpack',
            name='assets',
        ),
        migrations.RemoveField(
            model_name='moduleassetpack',
            name='source',
        ),
        migrations.RemoveField(
            model_name='module',
            name='assets',
        ),
        migrations.DeleteModel(
            name='ModuleAssetPack',
        ),
    ]
