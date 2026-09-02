from django.db import migrations

WRAPPER = '<ul class="partners">\n{{ items }}\n</ul>'
ITEM = '''<li>
    <div class="Img">
        <a href="{{ url }}"{{ link_attributes }}>
            <img src="{{ image }}" alt="{{ client_name }}">
        </a>
    </div>
    <div class="txt">{{ client_html }}</div>
    <div class="Clear"></div>
</li>'''
CSS = '''ul.partners { list-style: none; margin: 0; padding: 0; }
ul.partners > li { display: flex; gap: 24px; padding: 24px 0; border-bottom: 1px solid #ddd; }
ul.partners .Img { width: 180px; flex: 0 0 180px; }
ul.partners .Img img { max-width: 100%; height: auto; }
ul.partners .txt { flex: 1; }
ul.partners h3 { margin-top: 0; }
ul.partners h3 span { display: block; font-size: .75em; font-weight: normal; }
ul.partners .Clear { display: none; }
@media (max-width: 600px) { ul.partners > li { display: block; } ul.partners .Img { width: auto; margin-bottom: 15px; } }'''

def create_default_template(apps, schema_editor):
    PageTemplate = apps.get_model("partners", "PageTemplate")
    PageTemplate.objects.get_or_create(slug="default", defaults={"name": "Партнёры — основной", "wrapper_html": WRAPPER, "item_html": ITEM, "css": CSS})

def remove_default_template(apps, schema_editor):
    apps.get_model("partners", "PageTemplate").objects.filter(slug="default").delete()

class Migration(migrations.Migration):
    dependencies = [("partners", "0001_initial")]
    operations = [migrations.RunPython(create_default_template, remove_default_template)]
