# -*- coding: utf-8 -*-
"""
GVA file upload & download module API wrapper
Targets real GVA routes /fileUploadAndDownload/*
Docs: http://127.0.0.1:8888/swagger/index.html

Covers:
    - File list (paginated)
    - Upload (multipart/form-data)
    - Find by ID
    - Edit file name
    - Delete (single and batch)
    - Import from URL
"""
import io

from api.base_api import BaseApi


class FileApi(BaseApi):
    """
    File management client (based on real GVA endpoints)
    All operations go through admin auth by default (x-token injected by fixture)

    Note: GVA /fileUploadAndDownload/upload is multipart/form-data,
          we override Content-Type per request so the session default does not
          force application/json on the upload.
    """

    def get_file_list(self, page=1, page_size=10, keyword=""):
        """Paginated file list: POST /fileUploadAndDownload/getFileList"""
        return self.post("/fileUploadAndDownload/getFileList", json={
            "page": page,
            "pageSize": page_size,
            "keyword": keyword or "",
        })

    def upload(self, file_bytes, filename="test.txt", content_type="text/plain"):
        """
        Upload a file: POST /fileUploadAndDownload/upload (multipart/form-data)
        :param file_bytes: raw file bytes
        :param filename: name seen by server
        :param content_type: MIME type
        :return: requests.Response
        """
        files = {"file": (filename, io.BytesIO(file_bytes), content_type)}
        # Multipart upload: must NOT send application/json Content-Type from session
        # Setting Content-Type to None tells requests to let it auto-set multipart
        return self.session.post(
            "{}/fileUploadAndDownload/upload".format(self.base_url),
            files=files,
            timeout=self.timeout,
            headers={"Accept": "application/json", "Content-Type": None},
        )

    def find_file(self, file_id):
        """
        Find a file by ID: GET /fileUploadAndDownload/findFile?id=
        GVA spec: GET with id as query parameter (not POST body)
        """
        return self.get("/fileUploadAndDownload/findFile", params={"id": int(file_id)})

    def edit_file_name(self, file_id, new_name):
        """Edit a file's display name: POST /fileUploadAndDownload/editFileName"""
        return self.post("/fileUploadAndDownload/editFileName", json={
            "id": int(file_id),
            "name": new_name,
        })

    def delete_file(self, file_id):
        """Delete a single file by ID: POST /fileUploadAndDownload/deleteFile"""
        return self.post("/fileUploadAndDownload/deleteFile", json={"id": int(file_id)})

    def delete_files(self, file_ids):
        """Batch delete files: POST /fileUploadAndDownload/deleteFiles"""
        return self.post("/fileUploadAndDownload/deleteFiles", json={
            "ids": [int(i) for i in file_ids],
        })

    def import_url(self, url_items):
        """
        Import files from URL list: POST /fileUploadAndDownload/importURL
        :param url_items: list of dicts with at least {url, name}
        :return: requests.Response
        """
        return self.post("/fileUploadAndDownload/importURL", json=url_items)

    def list_oss_files(self, prefix=""):
        """List OSS objects (may fail if OSS not configured): POST /fileUploadAndDownload/listOssFiles"""
        return self.post("/fileUploadAndDownload/listOssFiles", json={
            "prefix": prefix,
        })
