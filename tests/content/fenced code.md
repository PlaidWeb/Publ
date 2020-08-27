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

/* this is a multi-line comment

It's important to make sure that this works
*/

int badlyFormattedFunction()
{
    // Who puts the open brace on its own line like that?

    // (lots of people)
    return 0;
}

int main() {
    std::cout << "Hello world" << std::endl;
    return 0;
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

def bar():
    return "bar" + foo()
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

Arguments:

```bash{code_highlight=False}
cat << EOF
This code has had highlighting disabled.

Test 1
Test 2
EOF
```



```html{code_number_links=False}
<span>This code has had number links disabled</span>
```

```{code_number_links=False}
No declared language, and disabled number links
```

```{code_number_links=True}
number links explicitly set True
but there is no declared language
```

```
\! first line has !
second line does not
```

```

! first line is blank
```

```
!
! empty caption
```