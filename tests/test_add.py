def add(a, b):
    return a + b


class TestAdd:

    def test_int(self):
        res = add(1, 3)
        assert res == 4

        def test_str(self):
            res = add("1", "3")
            assert res == "13"

        def test_list(self):
            res = add([1, 2], [3, 4])
            assert res == [1, 2, 3, 4]
