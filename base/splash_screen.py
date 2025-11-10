import os
import sys

import wx
import wx.adv


class SplashScreen(wx.adv.SplashScreen):
    def __init__(self):
        image_path = self._get_image_path()
        img = wx.Image(image_path, wx.BITMAP_TYPE_ANY)
        if img.IsOk():
            img = img.Scale(350, 350, wx.IMAGE_QUALITY_HIGH)
            bitmap = wx.Bitmap(img)
        else:

            bitmap = wx.Bitmap(image_path, wx.BITMAP_TYPE_JPEG)

        if bitmap.IsOk():
            dc = wx.MemoryDC()
            dc.SelectObject(bitmap)
            try:

                loading = "Loading..."
                load_font = wx.Font(
                    10, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL
                )
                dc.SetFont(load_font)
                lw, lh = dc.GetTextExtent(loading)
                lx = (bitmap.GetWidth() - lw) // 2
                ly = bitmap.GetHeight() - lh - 12
                dc.SetTextForeground(wx.Colour(0, 0, 0))
                dc.DrawText(loading, lx + 1, ly + 1)
                dc.SetTextForeground(wx.Colour(240, 240, 240))
                dc.DrawText(loading, lx, ly)
            finally:
                dc.SelectObject(wx.NullBitmap)

        super().__init__(
            bitmap,
            wx.adv.SPLASH_CENTRE_ON_SCREEN | wx.adv.SPLASH_NO_TIMEOUT,
            0,
            None,
            wx.ID_ANY,
        )

        self.Bind(wx.EVT_CLOSE, self.on_close)

    def _get_image_path(self):
        if getattr(sys, 'frozen', False):
            base_dir = sys._MEIPASS  # type: ignore
        else:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base_dir, "images", "fly400x400.jpeg")

    def on_close(self, event):
        self.Hide()
        event.Skip()

    def close(self):
        wx.CallAfter(self.Close)
