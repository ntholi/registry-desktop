from bs4 import BeautifulSoup

from base import get_logger
from base.browser import BASE_URL, Browser

logger = get_logger(__name__)


def scrape_modules(module_code: str) -> list[dict[str, str]]:
    browser = Browser()

    url = (
        f"{BASE_URL}/f_modulelist.php?"
        f"a_search=E&"
        f"z_ModuleCode=LIKE%2C%27%25%2C%25%27&"
        f"x_ModuleCode={module_code}&"
        f"sv_x_ModuleCode=&"
        f"s_x_ModuleCode=&"
        f"z_ModuleName=LIKE%2C%27%25%2C%25%27&"
        f"x_ModuleName=&"
        f"sv_x_ModuleName=&"
        f"s_x_ModuleName=&"
        f"Submit=Search"
    )

    response = browser.fetch(url)
    page = BeautifulSoup(response.text, "lxml")

    modules = []
    rows = page.select("table#ewlistmain tr")

    for row in rows:
        cells = row.select("td")
        if len(cells) < 5:
            continue

        code = cells[0].get_text(strip=True)
        name = cells[1].get_text(strip=True)
        status = cells[2].get_text(strip=True)
        timestamp = cells[4].get_text(strip=True)

        if not code or not name:
            continue

        view_link = row.select_one("a[href*='f_moduleview.php']")
        if view_link and "href" in view_link.attrs:
            href = str(view_link["href"])
            if "ModuleID=" in href:
                module_id = href.split("ModuleID=")[1].split("&")[0]
                modules.append(
                    {
                        "id": int(module_id),
                        "code": code,
                        "name": name,
                        "status": status,
                        "timestamp": timestamp,
                    }
                )

    return modules
