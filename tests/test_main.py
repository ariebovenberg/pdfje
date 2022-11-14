from pathlib import Path
from typing import cast

from pdfje import (
    Document,
    Font,
    Page,
    Rotation,
    Text,
    courier,
    helvetica,
    times_roman,
)

HERE = Path(__file__).parent


def test_hello(outfile):
    Document(
        [
            Page([Text("Hello", at=(200, 700)), Text("World", at=(300, 670))]),
            Page(),
            Page([Text("This is the last page!", at=(300, 600))]),
        ]
    ).to_path(outfile)


def test_rotate(outfile):
    Document(
        [
            Page(
                [Text(f"rotated {angle}", at=(400, 400))],
                rotate=cast(Rotation, angle),
            )
            for angle in (0, 90, 180, 270)
        ]
    ).to_path(outfile)


def test_different_fonts(outfile):
    dejavu = Font.from_path(HERE / "resources/DejaVuSansCondensed.ttf")
    roboto = Font.from_path(HERE / "resources/Roboto.ttf")
    Document(
        [
            Page(
                [
                    Text("Cheers, Cour®ier", at=(200, 500), font=courier),
                    Text("Hey hélvetica!", at=(200, 475), font=helvetica),
                    Text("Hí RobotὍ... ", at=(200, 450), font=roboto),
                    Text(
                        "Hello 𝌷 agaîn, DejaVü!",
                        at=(200, 425),
                        font=dejavu,
                    ),
                    Text("Good †imes", at=(200, 400), font=times_roman),
                    Text(
                        "(check that the text above can be copied!)",
                        at=(200, 375),
                    ),
                    Text("unknown char (builtin font): ∫", at=(200, 350)),
                    Text(
                        "unknown char (embedded font): ⟤",
                        at=(200, 325),
                        font=dejavu,
                    ),
                    Text(
                        "zalgo: t̶͈̓̕h̴̩̖͋̈́e̷̛̹ ̴̠͎̋̀p̷̦̔o̴̘͔̓n̸̞̙̐̕y̷̙̠̍ ̶̱̞̃h̶͈̮̅̆ë̸͍̟́̓ ̷̳̜̂c̵̢̡͋o̸̰̫͗̽m̷̨̿̕e̶̛̗̲͆s̸̨̭̐",  # noqa
                        at=(200, 300),
                        font=dejavu,
                    ),
                    Text("zero byte: \x00", at=(200, 275), font=dejavu),
                ]
            )
        ]
    ).to_path(outfile)
