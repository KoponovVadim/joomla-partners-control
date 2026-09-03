from pathlib import Path
from xml.etree import ElementTree
from zipfile import ZipFile

from django.test import SimpleTestCase


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "joomla_connector" / "plg_ajax_jpcconnector"
PACKAGE = (
    ROOT
    / "static"
    / "partners"
    / "downloads"
    / "plg_ajax_jpcconnector-1.0.0.zip"
)
REQUIRED_FILES = {
    "jpcconnector.php",
    "jpcconnector.xml",
    "script.php",
    "README.txt",
    "index.html",
}


class JoomlaConnectorPackageTests(SimpleTestCase):
    def test_manifest_targets_joomla_3_ajax_plugin(self):
        root = ElementTree.parse(SOURCE / "jpcconnector.xml").getroot()

        self.assertEqual(root.tag, "extension")
        self.assertEqual(root.attrib["type"], "plugin")
        self.assertEqual(root.attrib["group"], "ajax")
        self.assertEqual(root.attrib["version"], "3.10")
        self.assertEqual(root.findtext("version"), "1.0.0")
        self.assertEqual(
            root.find("./files/filename[@plugin='jpcconnector']").text,
            "jpcconnector.php",
        )

    def test_installable_zip_contains_current_sources(self):
        self.assertTrue(PACKAGE.is_file(), "Connector ZIP must be committed")

        with ZipFile(PACKAGE) as archive:
            self.assertEqual(set(archive.namelist()), REQUIRED_FILES)
            for name in REQUIRED_FILES:
                self.assertEqual(archive.read(name), (SOURCE / name).read_bytes())
