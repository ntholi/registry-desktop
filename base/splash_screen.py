import os

import wx
import wx.adv


class SplashScreen(wx.adv.SplashScreen):
    def __init__(self):
        image_path = self._get_image_path()
        bitmap = wx.Bitmap(image_path, wx.BITMAP_TYPE_JPEG)

        super().__init__(
            bitmap,
            wx.adv.SPLASH_CENTRE_ON_SCREEN | wx.adv.SPLASH_NO_TIMEOUT,
            0,
            None,
            wx.ID_ANY,
        )

        self.Bind(wx.EVT_CLOSE, self.on_close)

    def _get_image_path(self):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base_dir, "images", "fly400x400.jpeg")

    def on_close(self, event):
        self.Hide()
        event.Skip()

    def close(self):
        wx.CallAfter(self.Close)
