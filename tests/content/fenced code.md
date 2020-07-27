Title: Fenced code blocks
Date: 2020-06-18 15:42:24-07:00
Entry-ID: 2645
UUID: 76ddc3e6-41e0-5bb2-b635-bd3e1cb737a7

Code block in the intro:

```text
This is a text file.

It contains a lot of text.
```

Second code block in the intro:

```cpp
#include <cstdlib>

int main() {
    std::cout << "Hello world" << std::endl;
    return 0
}
```

```
This is text with no declared language.
```

.....


```
! a caption
This code block has no declared language.

Oh well!
```


```skdjflsjflsl
This code block declares an unknown language.

As a result, we treat it as plain text.
```

foo

```python
! invalid.py
def foo():
    return None + "bar"
```

bar

```markdown
\![literal escape on the first exclamation mark](foo)
```

```markdown

![a blank line works too]()
```

```markdown
! A caption line
![An image line]()
```
