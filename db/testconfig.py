from .db import db, conn_params


def test_config():
    assert db is not None


if __name__ == "__main__":
    test_config()
    for k in conn_params:
        if k != "password":
            print(k, "=>", conn_params[k])
